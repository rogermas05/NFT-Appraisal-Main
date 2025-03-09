#!/usr/bin/env python3
import asyncio
import os
import json
import re
import math
from pathlib import Path
import textwrap
import time
import structlog
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import queue
import threading

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json

# Import our custom confidence consensus components
from flare_ai_consensus.consensus.confidence.confidence_embeddings import (
    calculate_text_similarity, 
    extract_price_and_explanation
)

# Import sample data
from sample import sample_data
from dotenv import load_dotenv
from Backend.Ai.Sideinfo_api.sideinfo import main as get_nft_data
from Backend.Ai.cloud_confidence_index import run_confidence_consensus


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

ACCURACY_METRIC_DESIRED = True

# Parse data to compare accuracy
def accuracy_preparation(json_data):
    if json_data["sales_history"]:
        most_recent_transaction = json_data["sales_history"].pop(0)  # Removes and stores the first (latest) entry
        formatted_date = datetime.strptime(most_recent_transaction["date"], "%Y-%m-%d %H:%M:%S").strftime("%B, %Y")
    
    return most_recent_transaction["price_usd"], formatted_date, json_data

if ACCURACY_METRIC_DESIRED:
    ACTUAL_VALUE, DATE_TO_PREDICT, sample_data = accuracy_preparation(sample_data)


# Configure structlog for better formatting
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.JSONRenderer(indent=2, sort_keys=True)
    ]
)

logger = structlog.get_logger()

# Improved challenge prompts that encourage refinement rather than radical changes
CHALLENGE_PROMPTS = [
    "Based on your analysis, evaluate whether you need to refine your price estimate. Consider a variety of market scenarios and use the data to identify what price estimate is most appropriate.",
    
    "Your price estimate might be unreasonable, could you provide a more nuanced analysis to support your estimate? Alternatively, you may wish to change your estimate.",
    
    "What factors might you have missed out on? Please reconsider your valuation with these factors in mind."
]

# Global event queue for streaming updates
event_queue = queue.Queue()

def send_event(event_type, data):
    """Add an event to the queue for streaming"""
    event_data = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    event_queue.put(event_data)
    return event_data

def print_colored(text, color=None):
    """Print text with ANSI color codes and send as stream event"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }
    
    if color and color in colors:
        print(f"{colors[color]}{text}{colors['reset']}")
    else:
        print(text)
        
    # Send as log event to the stream
    send_event("log", {"message": text, "color": color})

def format_and_print_responses(responses, title="Model Responses"):
    """Format and print model responses nicely in the terminal and send as stream event"""
    terminal_width = 80
    separator = "=" * terminal_width
    
    print_colored(f"\n{separator}", "cyan")
    print_colored(f"{title.center(terminal_width)}", "cyan")
    print_colored(f"{separator}\n", "cyan")
    
    formatted_responses = {}
    
    for model_id, response in responses.items():
        print_colored(f"Model: {model_id}", "yellow")
        
        # Extract price and explanation
        price, explanation = properly_extract_json_price(str(response))
        if price is not None:
            print_colored(f"Extracted price: ${price:.2f}", "cyan")
            formatted_responses[model_id] = {
                "response": str(response),
                "price": price,
                "explanation": explanation
            }
        else:
            formatted_responses[model_id] = {
                "response": str(response),
                "price": None,
                "explanation": None
            }
        
        # Format and wrap the response text
        wrapped_text = textwrap.fill(str(response), width=terminal_width-4)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        print_colored(f"{'-' * terminal_width}", "blue")
    
    # Send detailed model responses as a stream event
    send_event("model_responses", {
        "title": title,
        "responses": formatted_responses
    })

def convert_to_string(obj):
    """Safely convert any object to a string"""
    if isinstance(obj, str):
        return obj
    
    if isinstance(obj, dict):
        if 'content' in obj:
            return str(obj.get('content', ''))
        elif 'text' in obj:
            return str(obj.get('text', ''))
        elif 'message' in obj and isinstance(obj['message'], dict) and 'content' in obj['message']:
            return str(obj['message']['content'])
    
    # Fallback to string representation
    try:
        return str(obj)
    except:
        return "[Error: Could not convert object to string]"


def properly_extract_json_price(text):
    """
    Properly extract the price from a JSON response by first trying to parse as JSON.
    
    Args:
        text: The model's response as text
        
    Returns:
        tuple: (price as float or None, explanation as string or None)
    """
    # Clean up any potential code block markers
    cleaned_text = text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = re.sub(r'^```json\s*', '', cleaned_text)
        cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
    elif cleaned_text.startswith("```"):
        cleaned_text = re.sub(r'^```\s*', '', cleaned_text)
        cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
    
    # Try to parse as JSON
    try:
        # First try to parse the whole text
        data = json.loads(cleaned_text)
        if isinstance(data, dict):
            # Extract price
            if "price" in data:
                try:
                    price = float(data["price"])
                    explanation = data.get("explanation", "")
                    return price, explanation
                except (ValueError, TypeError):
                    pass
    except json.JSONDecodeError:
        # If that fails, try to find and parse just the JSON part
        json_pattern = r'({[^{}]*"price"[^{}]*})'
        match = re.search(json_pattern, cleaned_text)
        if match:
            try:
                json_part = match.group(1)
                data = json.loads(json_part)
                if "price" in data:
                    return float(data["price"]), data.get("explanation", "")
            except (json.JSONDecodeError, ValueError):
                pass
    
    # If JSON parsing fails, fall back to regex
    print_colored("JSON parsing failed, falling back to regex extraction", "yellow")
    
    # Look for {"price": 1234} pattern
    price_match = re.search(r'"price"\s*:\s*([0-9,]+\.?[0-9]*)', text)
    if price_match:
        try:
            price = float(price_match.group(1).replace(',', ''))
            # Try to extract explanation
            explanation_match = re.search(r'"explanation"\s*:\s*"([^"]+)"', text)
            explanation = explanation_match.group(1) if explanation_match else None
            return price, explanation
        except (ValueError, TypeError):
            pass
    
    # Look for dollar amounts as last resort
    dollar_match = re.search(r'\$([0-9,]+\.?[0-9]*)', text)
    if dollar_match:
        try:
            price = float(dollar_match.group(1).replace(',', ''))
            return price, None
        except (ValueError, TypeError):
            pass
    
    return None, None


async def patch_provider_for_logging(provider):
    """Patch the provider's _post method to log request/response details"""
    original_post = provider._post
    
    async def logged_post(endpoint, json_payload):
        logger.info("API request", endpoint=endpoint, max_tokens=json_payload.get('max_tokens'))
        print_colored(f"Request to {endpoint}: max_tokens={json_payload.get('max_tokens')}", "blue")
        response = await original_post(endpoint, json_payload)
        logger.info("API response received", endpoint=endpoint, status="success")
        return response
    
    provider._post = logged_post
    return provider


async def send_initial_round(provider, consensus_config, initial_conversation):
    """Get initial responses from all models and display responses as they come in"""
    logger.info("Getting initial responses from models")
    initial_responses = {}
    
    for model in consensus_config.models:
        model_id = model.model_id
        print_colored(f"Requesting initial response from {model_id}...", "blue")
        
        # Create payload
        payload = {
            "model": model_id,
            "messages": initial_conversation,
            "max_tokens": model.max_tokens,
            "temperature": model.temperature,
        }
        
        # Send request and immediately show response (no concurrent processing)
        try:
            print_colored(f"Waiting for {model_id} to respond...", "blue")
            response = await provider.send_chat_completion(payload)
            text = response.get("choices", [])[0].get("message", {}).get("content", "")
            initial_responses[model_id] = text
            
            # Immediately display this model's response
            print_colored(f"\n----- Initial Response from {model_id} -----", "green")
            
            # Extract price and explanation
            price, explanation = properly_extract_json_price(text)
            if price is not None:
                print_colored(f"Extracted price: ${price:.2f}", "cyan")
            
            # Show truncated response
            max_preview_chars = 500
            preview = text if len(text) <= max_preview_chars else text[:max_preview_chars] + "..."
            print(preview)
            print_colored("-" * 40, "green")
            
        except Exception as e:
            logger.error(f"Error getting response from {model_id}: {e}")
            error_msg = f"Error: {str(e)}"
            initial_responses[model_id] = error_msg
            print_colored(f"Error getting response from {model_id}: {e}", "red")
        
    return initial_responses


async def send_challenge_round(provider, consensus_config, initial_conversation, challenge_prompt, initial_responses):
    """Send challenge prompts to all models and display responses as they come in"""
    logger.info("Sending challenge prompts to models")
    challenge_responses = {}
    
    for model in consensus_config.models:
        model_id = model.model_id
        print_colored(f"Sending challenge to {model_id}...", "blue")
        
        # Get the model's original response and extract price
        original_response = initial_responses.get(model_id, "")
        
        # Create contextual challenge prompt that includes original response
        contextualized_prompt = f"""
        Your previous price estimation analysis was was {original_response}.

        {challenge_prompt}

        Remember to maintain the same JSON format with 'price' and 'explanation' fields.
        """
        
        print(contextualized_prompt)
        
        # Build conversation with challenge
        conversation = initial_conversation.copy()
        conversation.append({"role": "user", "content": contextualized_prompt})
        
        # Create payload
        payload = {
            "model": model_id,
            "messages": conversation,
            "max_tokens": model.max_tokens,
            "temperature": model.temperature,
        }
        
        # Send request and immediately show response (no concurrent processing)
        try:
            print_colored(f"Waiting for {model_id} to respond...", "blue")
            response = await provider.send_chat_completion(payload)
            text = response.get("choices", [])[0].get("message", {}).get("content", "")
            challenge_responses[model_id] = text
            
            # Immediately display this model's response
            print_colored(f"\n----- Response from {model_id} -----", "green")
            
            # Extract price and explanation
            price, explanation = properly_extract_json_price(text)
            if price is not None:
                print_colored(f"Extracted price: ${price:.2f}", "cyan")
            
            # Show truncated response
            max_preview_chars = 500
            preview = text if len(text) <= max_preview_chars else text[:max_preview_chars] + "..."
            print(preview)
            print_colored("-" * 40, "green")
            
        except Exception as e:
            logger.error(f"Error getting challenge response from {model_id}: {e}")
            error_msg = f"Error: {str(e)}"
            challenge_responses[model_id] = error_msg
            print_colored(f"Error getting response from {model_id}: {e}", "red")
    
    return challenge_responses


async def analyze_model_responses(initial_responses, challenge_responses):
    """Analyze how models respond to challenges"""
    analysis = {}
    
    for model_id in initial_responses:
        # Get initial and challenge responses
        initial = initial_responses.get(model_id, "")
        challenge = challenge_responses.get(model_id, "")
        
        # Skip if either response is missing
        if not initial or not challenge:
            print_colored(f"Skipping analysis for {model_id} due to missing responses", "red")
            continue
            
        # Extract prices and explanations using proper JSON parsing
        initial_price, initial_explanation = properly_extract_json_price(initial)
        challenge_price, challenge_explanation = properly_extract_json_price(challenge)
        
        # Fall back to regex extraction if parsing fails
        if initial_price is None:
            tmp_price, tmp_explanation = extract_price_and_explanation(initial)
            initial_price = tmp_price
            initial_explanation = tmp_explanation or ""
            
        if challenge_price is None:
            tmp_price, tmp_explanation = extract_price_and_explanation(challenge)
            challenge_price = tmp_price
            challenge_explanation = tmp_explanation or ""
        
        # Ensure we have explanation strings
        initial_explanation = initial_explanation or ""
        challenge_explanation = challenge_explanation or ""
        
        # Calculate price change with improved formula
        if initial_price == 0 and challenge_price == 0:
            price_change = 0
        elif initial_price == 0:
            price_change = 0.8  # Cap at 80% for maximum change
        else:
            # Calculate relative price change
            price_change = min(abs(challenge_price - initial_price) / initial_price, 1)
            
            
     
            
        # Calculate price stability (inverse of price change)
        price_stability = 1 - price_change
        
        # Calculate text similarity
        text_similarity = calculate_text_similarity(initial_explanation, challenge_explanation)
        
        # Calculate confidence score using weighted formula
        # 30% weight on text similarity, 70% on price stability
        confidence_score = (0.3 * text_similarity) + (0.7 * price_stability)
        
        # Ensure score is in [0,1] range
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        # Store analysis
        analysis[model_id] = {
            "initial_price": initial_price,
            "challenge_price": challenge_price,
            "price_change": price_change,
            "price_stability": price_stability,
            "text_similarity": text_similarity,
            "confidence_score": confidence_score
        }
        
        # Log results
        print_colored(f"\nModel: {model_id}", "yellow")
        print_colored(f"Initial price: ${initial_price:.2f}", "cyan")
        print_colored(f"Challenge price: ${challenge_price:.2f}", "cyan")
        print_colored(f"Raw change: {abs(challenge_price - initial_price) / max(initial_price, 1):.2%}", "cyan")
        print_colored(f"Price change: {price_change:.2%}", "magenta")
        print_colored(f"Price stability: {price_stability:.4f}", "magenta")
        print_colored(f"Text similarity: {text_similarity:.4f}", "magenta")
        print_colored(f"Formula: 0.3 * {text_similarity:.4f} + 0.7 * {price_stability:.4f} = {confidence_score:.4f}", "blue")
        print_colored(f"Confidence score: {confidence_score:.4f}", "green")
        
    return analysis


async def weighted_aggregation(provider, aggregator_config, model_responses, analysis):
    """
    Provide aggregator model with confidence scores and let it determine the final price.
    We don't calculate a weighted average ourselves, but instead pass the weights to the model.
    """
    # Calculate weights based on confidence scores
    confidence_scores = {model_id: data["confidence_score"] for model_id, data in analysis.items()}
    
    # Calculate total confidence for normalization
    total_confidence = sum(confidence_scores.values())
    
    # Normalize weights to ensure they sum to 1
    if total_confidence > 0:
        weights = {model_id: score / total_confidence for model_id, score in confidence_scores.items()}
    else:
        # Equal weights if all confidence scores are 0
        weight = 1.0 / max(len(confidence_scores), 1)
        weights = {model_id: weight for model_id in confidence_scores}
    
    # Verify that weights sum to 1
    weight_sum = sum(weights.values())
    print_colored(f"Total weight sum: {weight_sum:.6f}", "blue")
    
    # Apply a small correction if needed due to floating point errors
    if abs(weight_sum - 1.0) > 0.000001:
        correction_factor = 1.0 / weight_sum
        weights = {model_id: w * correction_factor for model_id, w in weights.items()}
        print_colored(f"Applied correction factor: {correction_factor}", "yellow")
        print_colored(f"New weight sum: {sum(weights.values()):.6f}", "blue")
    
    # Calculate standard statistics for informational purposes only
    prices = [analysis[model_id]["challenge_price"] for model_id in analysis]
    if prices:
        valid_prices = [p for p in prices if p is not None and p > 0]
        if valid_prices:
            mean_price = statistics.mean(valid_prices)
            median_price = statistics.median(valid_prices)
            std_dev = statistics.stdev(valid_prices) if len(valid_prices) > 1 else 0
        else:
            mean_price = 0
            median_price = 0
            std_dev = 0
    else:
        mean_price = 0
        median_price = 0
        std_dev = 0
        
    
    # Log the normalized weights and prices
    print_colored("\nModel Weights and Prices:", "cyan")
    for model_id, weight in weights.items():
        if model_id in analysis:
            price = analysis[model_id]["challenge_price"]
            print_colored(f"Model: {model_id}", "cyan")
            print_colored(f"- Weight: {weight:.4f}", "blue") 
            print_colored(f"- Price: ${price:.2f}", "blue")
    
    print_colored(f"\nStatistics (for information only):", "cyan")
    print_colored(f"Mean price: ${mean_price:.2f}", "cyan")
    print_colored(f"Median price: ${median_price:.2f}", "cyan")
    print_colored(f"Standard deviation: ${std_dev:.2f}", "cyan")
    
    # Create weighted aggregation text for the aggregator
    weighted_responses_text = []
    for model_id, challenge_response in model_responses.items():
        if model_id in weights and model_id in analysis:
            weight = weights[model_id]
            price = analysis[model_id]["challenge_price"]
            response_text = f"Model: {model_id} (Weight: {weight:.4f}, Price: ${price:.2f})\n{challenge_response}"
            weighted_responses_text.append(response_text)
    
    weighted_text = "\n\n---\n\n".join(weighted_responses_text)
    
    # Build messages for the aggregator
    messages = []
    messages.extend(aggregator_config.context)
    
    # Add weighted responses with statistics
    system_message = {
        "role": "system", 
        "content": (
            f"You are synthesizing multiple NFT appraisals from different models. Each model has been assigned a confidence weight based on how consistent their analysis remained when challenged.\n\n"
            f"A higher weight means the model's response should be given more consideration in your final synthesis.\n\n"
            f"Here are the model responses with their confidence weights:\n\n"
            f"{weighted_text}"
        )
    }
    messages.append(system_message)
    
    # Add aggregator prompt with explicit JSON structure requirement
    aggregator_prompt = {
        "role": "user",
        "content": """Based on the model responses and their assigned confidence weights, provide your final appraisal of the NFT's value.

Your response MUST be in JSON format with the following structure:
{
  "price": [Final price in USD as a number],
  "explanation": "[Brief explanation in 2-3 sentences]"
}

Important guidelines:
1. Instead, use your expertise to determine the most reasonable price based on:
   - The quality of each model's reasoning
   - The confidence weights assigned to each model
   - Recent sales data emphasized in the responses
   - The NFT's rarity and market trends
2. Your price should reflect your best judgment of the true value, informed by the weighted model responses
3. Your explanation should be concise but informative

Do not include any text outside the JSON structure or any markdown code blocks.
"""
    }
    messages.append(aggregator_prompt)
    
    # Send request to the aggregator model
    payload = {
        "model": aggregator_config.model.model_id,
        "messages": messages,
        "max_tokens": aggregator_config.model.max_tokens,
        "temperature": aggregator_config.model.temperature,
    }
    
    print_colored(f"Sending aggregation request to {aggregator_config.model.model_id}...", "blue")
    
    response = await provider.send_chat_completion(payload)
    aggregated_text = response.get("choices", [])[0].get("message", {}).get("content", "")
    
    # Clean up JSON if needed
    aggregated_text = aggregated_text.strip()
    if aggregated_text.startswith('```json'):
        aggregated_text = re.sub(r'^```json\s*', '', aggregated_text)
    if aggregated_text.endswith('```'):
        aggregated_text = re.sub(r'\s*```$', '', aggregated_text)
    aggregated_text = aggregated_text.strip()
    
    # Try to parse the JSON to validate it
    try:
        result_json = json.loads(aggregated_text)
        
        # Ensure we have the basic required fields
        if "price" not in result_json:
            result_json["price"] = median_price  # Use median as a fallback
        
        if "explanation" not in result_json:
            result_json["explanation"] = "Final price estimate based on weighted model contributions."
            
        # Add our calculated statistics and model data
        result_json["standard_deviation"] = std_dev
        result_json["models"] = {}
        
        predicted_price = result_json["price"]
        error_accuracy = abs((ACTUAL_VALUE - predicted_price)) / ACTUAL_VALUE
        accuracy = 1 - error_accuracy
        
        print_colored(f"Predicted Price: ${predicted_price:.2f}", "green")
        print_colored(f"Actual Price: ${ACTUAL_VALUE:.2f}", "green")
        print_colored(f"Accuracy: {accuracy:.2%}", "green")
        
        result_json["accuracy"] = accuracy
        
        for model_id, data in analysis.items():
            result_json["models"][model_id] = {
                "text_similarity": data["text_similarity"],
                "price_change": data["price_change"],
                "weight": weights[model_id]
            }
            
        # Add Final Confidence score and Standard Deviation of Weights
        weights = [weights.get(model_id, 0) for model_id in analysis]
        print("WEIGHTS: ", weights)
        
        if weights and len(weights) > 1:
            weights_std_dev = statistics.stdev(weights)
            cv = weights_std_dev / (sum(weights) / len(weights) )
            confidence = 1.0 - min(cv, 1.0)
            final_confidence = max(0.1, min(0.9, confidence))
        
            result_json["final_confidence_score"] = final_confidence
            result_json["weights_standard_deviation"] = weights_std_dev
            
        # Convert back to JSON string
        aggregated_text = json.dumps(result_json, indent=2)
        
    except json.JSONDecodeError as e:
        print_colored(f"Error parsing aggregator response as JSON: {e}", "red")
        print_colored("Creating fallback JSON output", "yellow")
        
        # Create our own JSON if parsing fails
        models_json = {}
        for model_id, data in analysis.items():
            models_json[model_id] = {
                "text_similarity": data["text_similarity"],
                "price_change": data["price_change"],
                "weight": weights[model_id]
            }
            
        result_json = {
            "price": median_price,  # Use median as a reasonable fallback
            "explanation": "Final price estimate based on analysis of model responses, with higher weight given to more consistent models.",
            "standard_deviation": std_dev,
            "models": models_json
        }
        
        aggregated_text = json.dumps(result_json, indent=2)
    
    return aggregated_text

def generate_sse_events():
    """Generate Server-Sent Events for streaming"""
    # Send initial connection event
    yield f"event: connect\ndata: {json.dumps({'connected': True, 'timestamp': datetime.now().isoformat()})}\n\n"
    
    # Continue sending events from the queue
    while True:
        try:
            # Try to get an event from the queue with a timeout
            event = event_queue.get(timeout=1)
            event_type = event["type"]
            event_data = json.dumps(event)
            
            # Format as SSE
            yield f"event: {event_type}\ndata: {event_data}\n\n"
            
            # If this is a final consensus event, close the connection
            if event_type == "final_consensus":
                # Send a final closing event
                final_event = {
                    "type": "close",
                    "data": {"message": "Stream complete", "timestamp": datetime.now().isoformat()}
                }
                yield f"event: close\ndata: {json.dumps(final_event)}\n\n"
                break
                
        except queue.Empty:
            # Send a keepalive comment every second if queue is empty
            yield ": keepalive\n\n"
        except Exception as e:
            # If any error occurs, send it as an event and continue
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

# Update the Flask routes to include streaming endpoint
@app.route('/confidence_appraise/stream', methods=['GET'])
def appraise_nft_stream_api():
    """Streaming API endpoint to appraise an NFT with real-time updates using confidence consensus"""
    # Clear the event queue for a fresh start
    while not event_queue.empty():
        event_queue.get()
    
    # Get parameters from the request
    contract_address = request.args.get('contract_address')
    token_id = request.args.get('token_id')
    date_to_predict = request.args.get('date')
    
    if not contract_address or not token_id:
        # Send error event and return error response
        error_msg = "Missing contract_address or token_id parameter"
        send_event("error", {"message": error_msg})
        return jsonify({
            "error": error_msg,
            "price": 0,
            "text": "Error: Missing required parameters",
            "standard_deviation": 0,
            "total_confidence": 0
        }), 400
    
    # Start the processing in a background thread
    def run_processing():
        asyncio.run(run_confidence_consensus(contract_address, token_id, date_to_predict))
    
    processing_thread = threading.Thread(target=run_processing)
    processing_thread.daemon = True
    processing_thread.start()
    
    # Return streaming response
    return Response(
        stream_with_context(generate_sse_events()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )

# Update the main function to run the Flask app
def main():
    # Set the port from environment variable or use default
    port = int(os.environ.get('PORT', 8082))
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Import needed modules for statistics
    import statistics
    main()