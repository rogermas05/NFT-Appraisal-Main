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

# Load environment variables
load_dotenv()

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
    "Based on your analysis, could you refine your price estimate? Please consider both bullish and bearish market scenarios, focusing on the most recent sales data.",
    
    "Could you revisit your price estimate, taking into account the NFT's rarity rank and recent sales patterns? A slightly more detailed analysis would be helpful.",
    
    "Your price estimate seems reasonable, but could you provide a more nuanced analysis that considers potential market fluctuations? Please maintain a focus on recent transaction data.",
    
    "What factors might cause your price estimate to change in either direction? Please reconsider your valuation with these factors in mind.",
    
    "Recent market trends suggest some volatility in NFT valuations. Could you refine your estimate considering both optimistic and conservative scenarios?"
]

def print_colored(text, color=None):
    """Print text with ANSI color codes"""
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


def format_and_print_responses(responses, title="Model Responses"):
    """Format and print model responses nicely in the terminal"""
    terminal_width = 80
    separator = "=" * terminal_width
    
    print(f"\n{separator}")
    print(f"{title.center(terminal_width)}")
    print(f"{separator}\n")
    
    for model_id, response in responses.items():
        print(f"Model: {model_id}")
        
        # Ensure response is a string
        response_text = convert_to_string(response)
        
        # Extract price and explanation from response
        price, explanation = properly_extract_json_price(response_text)
        if price is not None:
            print(f"Extracted price: ${price:.2f}")
        
        # Format and wrap the response text
        try:
            wrapped_text = textwrap.fill(response_text, width=terminal_width-4)
            indented_text = textwrap.indent(wrapped_text, "  ")
            print(indented_text)
        except Exception as e:
            print(f"  Error formatting response: {e}")
            print(f"  Raw response: {response_text[:500]}...")
            
        print(f"{'-' * terminal_width}")


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
        original_price, _ = properly_extract_json_price(original_response)
        
        # If price couldn't be extracted, try the fallback method
        if original_price is None:
            tmp_price, _ = extract_price_and_explanation(original_response)
            original_price = tmp_price
        
        price_str = f"${original_price:.2f}" if original_price is not None else "unknown"
        
        # Create contextual challenge prompt that includes original response
        contextualized_prompt = f"""
        Your previous price estimate was {price_str}.

        {challenge_prompt}

        
        Remember to maintain the same JSON format with 'price' and 'explanation' fields.
        """
        
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
        # try:
        #     print_colored(f"Waiting for {model_id} to respond...", "blue")
        #     response = await provider.send_chat_completion(payload)
        #     text = response.get("choices", [])[0].get("message", {}).get("content", "")
        #     challenge_responses[model_id] = text
            
        #     # Immediately display this model's response
        #     print_colored(f"\n----- Response from {model_id} -----", "green")
            
        #     # Extract price and explanation
        #     price, explanation = properly_extract_json_price(text)
        #     if price is not None:
        #         print_colored(f"Extracted price: ${price:.2f}", "cyan")
            
        #     # Show truncated response
        #     max_preview_chars = 500
        #     preview = text if len(text) <= max_preview_chars else text[:max_preview_chars] + "..."
        #     print(preview)
        #     print_colored("-" * 40, "green")
            
        # except Exception as e:
        #     logger.error(f"Error getting challenge response from {model_id}: {e}")
        #     error_msg = f"Error: {str(e)}"
        #     challenge_responses[model_id] = error_msg
        #     print_colored(f"Error getting response from {model_id}: {e}", "red")
    
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
            # Calculate relative price change with softening function
            relative_change = abs(challenge_price - initial_price) / max(initial_price, 1)
            # Apply a square root transformation to reduce impact of large changes
            # Cap at 80% to prevent extreme penalties
            price_change = min(0.8, math.sqrt(min(1, relative_change)))
            
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
        print_colored(f"Softened price change: {price_change:.2%}", "magenta")
        print_colored(f"Price stability: {price_stability:.4f}", "magenta")
        print_colored(f"Text similarity: {text_similarity:.4f}", "magenta")
        print_colored(f"Formula: 0.3 * {text_similarity:.4f} + 0.7 * {price_stability:.4f} = {confidence_score:.4f}", "blue")
        print_colored(f"Confidence score: {confidence_score:.4f}", "green")
        
    return analysis


async def weighted_aggregation(provider, aggregator_config, model_responses, analysis):
    """Perform weighted aggregation based on confidence scores"""
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
    
    # Calculate price statistics
    prices = [analysis[model_id]["challenge_price"] for model_id in analysis]
    
    # Handle outliers by removing extreme values
    if len(prices) >= 3:
        # Sort prices
        sorted_prices = sorted(prices)
        # Calculate Q1 and Q3
        q1_index = len(sorted_prices) // 4
        q3_index = 3 * len(sorted_prices) // 4
        q1 = sorted_prices[q1_index]
        q3 = sorted_prices[q3_index]
        # Calculate IQR and bounds
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        # Filter out outliers
        filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]
        
        if filtered_prices:
            print_colored(f"Removed {len(prices) - len(filtered_prices)} outliers", "yellow")
            prices = filtered_prices
    
    # Only calculate if we have valid prices
    if prices:
        # Filter out None or zero values
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
    
    # Calculate weighted price - use challenge prices
    weighted_price = 0
    for model_id, weight in weights.items():
        if model_id in analysis:
            price = analysis[model_id]["challenge_price"]
            if price is not None:
                weighted_price += price * weight
    
    # Log the normalized weights and prices
    print_colored("\nWeighted Calculation Details:", "cyan")
    for model_id, weight in weights.items():
        if model_id in analysis:
            price = analysis[model_id]["challenge_price"]
            weighted_contribution = price * weight
            print_colored(f"Model: {model_id}", "cyan")
            print_colored(f"- Weight: {weight:.4f}", "blue")
            print_colored(f"- Price: ${price:.2f}", "blue")
            print_colored(f"- Weighted Contribution: ${weighted_contribution:.2f}", "green")
    
    print_colored(f"\nWeighted price: ${weighted_price:.2f}", "green")
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
            f"Aggregated responses from multiple models with confidence-based weights:\n\n"
            f"Weighted price: ${weighted_price:.2f}\n"
            f"Mean price: ${mean_price:.2f}\n"
            f"Median price: ${median_price:.2f}\n"
            f"Standard deviation: ${std_dev:.2f}\n\n"
            f"{weighted_text}"
        )
    }
    messages.append(system_message)
    
    # Add aggregator prompt with explicit JSON structure requirement
    aggregator_prompt = {
        "role": "user",
        "content": """You are synthesizing multiple NFT appraisals into a final estimate. Every model has been assigned a confidence weight based on how consistent their analysis has remained when challenged.

Your response MUST be in JSON format with the following structure (exactly matching this format):
{
  "price": [Final price in USD as a number],
  "explanation": "[Brief explanation in 2-3 sentences]",
  "standard_deviation": [Standard deviation value],
  "models": {
    "[model_name_1]": {
      "text_similarity": [similarity score],
      "price_change": [price change percentage],
      "weight": [calculated weight]
    },
    "[model_name_2]": {
      "text_similarity": [similarity score],
      "price_change": [price change percentage],
      "weight": [calculated weight]
    }
  }
}

Do not include any other text outside this JSON structure. Do not include markdown code blocks. Your entire response should be just a valid JSON object.
Use the weights to determine each model's contribution, giving more weight to models with higher confidence scores. The final price should reflect the weighted average of the model prices.
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
    
    # Try to parse the JSON
    try:
        result_json = json.loads(aggregated_text)
        
        # Ensure proper structure
        if "models" not in result_json:
            result_json["models"] = {}
            
        # Make sure all models are included with correct data
        for model_id, data in analysis.items():
            if model_id not in result_json["models"]:
                result_json["models"][model_id] = {}
                
            # Update model data
            result_json["models"][model_id]["text_similarity"] = data["text_similarity"]
            result_json["models"][model_id]["price_change"] = data["price_change"]
            result_json["models"][model_id]["weight"] = weights[model_id]
        
        # Add standard deviation if missing
        if "standard_deviation" not in result_json:
            result_json["standard_deviation"] = std_dev
            
        # Override price with our calculated weighted price
        result_json["price"] = weighted_price
            
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
            "price": weighted_price,
            "explanation": f"Final price estimate of ${weighted_price:.2f} based on weighted model contributions. Higher weights were given to models with greater consistency between initial and challenged responses.",
            "standard_deviation": std_dev,
            "models": models_json
        }
        
        aggregated_text = json.dumps(result_json, indent=2)
    
    return aggregated_text


async def main():
    import random
    
    # Load API key from environment variable
    api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    if not api_key:
        print_colored("Error: OPEN_ROUTER_API_KEY environment variable not set.", "red")
        print("Please set your OpenRouter API key in your .env file")
        return

    # Initialize the settings
    settings = Settings()
    
    # Create paths for configuration and data
    config_path = Path("config")
    config_path.mkdir(exist_ok=True)
    
    # Load or create the consensus configuration
    config_file = config_path / "consensus_config.json"
           
    # Load the configuration
    config_json = load_json(config_file)
    settings.load_consensus_config(config_json)
    
    # Create the OpenRouter provider
    provider = AsyncOpenRouterProvider(
        api_key=api_key,
        base_url=settings.open_router_base_url
    )
    
    # Patch the provider for better logging
    provider = await patch_provider_for_logging(provider)
    
    # Define the NFT appraisal conversation
    nft_appraisal_conversation = [
        {
            "role": "system",
            "content": """You are an expert at conducting NFT appraisals, and your goal is to output the price in USD value of the NFT at this specific date, which is March, 2025. You will be given pricing history and other metadata about the NFT and will have to extrapolate and analyze the trends from the data. Your response MUST be in JSON format starting with a single value of price in USD, followed by a detailed explanation of your reasoning.

            The sample data that you will be given will be in this input format, although the values will be different. Use it to understand how the data is laid out and what each entry means. Your analysis and appraisal should be more nuanced, smart, and data-driven than the example. 
            
            Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers

            In the JSON, the price of Ethereum (price_ethereum) was how much Ethereum was paid at the time and the price in USD (price_usd) is the price of that Ethereum at the time of the sale in USD. 

            Example Input:
            {
                "name": "Art Blocks",
                "token_id": "78000956",
                "token_address": "0xa7d8d9ef8d8ce8992df33d8b8cf4aebabd5bd270",
                "metadata": {
                    "symbol": "BLOCKS",
                    "rarity_rank": "None",
                    "rarity_percentage": "None",
                    "amount": "1"
                },
                "sales_history": [
                    {
                        "price_ethereum": 24.61,
                        "price_usd": 61914.7812,
                        "date": "2025-03-03 17:49:35"
                    },
                    {
                        "price_ethereum": 85.0,
                        "price_usd": 108403.25579,
                        "date": "2022-12-13 19:04:11"
                    },
                    {
                        "price_ethereum": 0.17,
                        "price_usd": 422.72201,
                        "date": "2021-06-11 09:21:07"
                    }
                ]
            }

            Example Output:
            {
                "price": 67240,
                "explanation": "Based on the sales history, the price of the NFT has been increasing over time. The most recent sale was for 24.61 ETH, which is worth $61914.7812 at the time of the sale. The previous sale was for 85 ETH, which is worth $108403.25579 at the time of the sale. The first sale was for 0.17 ETH, which is worth $422.72201 at the time of the sale. Based on this data, I estimate that the price of the NFT is currently $67240. Additional context on the rarity would help improve the response and the price estimate, however, with the given data, this seems a reasonable estimate for this date."
            }
            
            """
            },
        {
            "role": "user",
            "content": f"Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers. Here is the sample data: {sample_data}. "
        }
    ]
    
    print_colored("\nSending NFT appraisal request to multiple models...", "magenta")
    print_colored("Using sample data for NFT appraisal", "cyan")
    
    # Display configuration summary
    for model in settings.consensus_config.models:
        print_colored(f"Model: {model.model_id} (max_tokens: {model.max_tokens})", "yellow")
    
    aggregator_model = settings.consensus_config.aggregator_config.model
    print_colored(f"Aggregator: {aggregator_model.model_id} (max_tokens: {aggregator_model.max_tokens})", "yellow")
    
    try:
        # Step 1: Get initial model responses
        print_colored("\nGetting initial model responses...", "magenta")
        logger.info("Starting initial model response collection")
        initial_responses = await send_initial_round(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation
        )
        
        # Display individual responses
        format_and_print_responses(initial_responses, "<INITIAL MODEL RESPONSES>")
        logger.info("Initial responses collected", model_count=len(initial_responses))
        
        # Step 2: Select a challenge prompt
        challenge_prompt = random.choice(CHALLENGE_PROMPTS)
        print_colored(f"\nSelected challenge prompt: '{challenge_prompt}'", "blue")
        
        # Step 3: Send challenge to all models, including their original responses
        print_colored("\nSending challenge prompt to all models...", "magenta")
        challenge_responses = await send_challenge_round(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation,
            challenge_prompt=challenge_prompt,
            initial_responses=initial_responses
        )
        
        # Display challenge responses
        format_and_print_responses(challenge_responses, "<CHALLENGE RESPONSES>")
        
        # Step 4: Analyze how models respond to the challenge
        print_colored("\nAnalyzing model responses to challenge...", "magenta")
        analysis = await analyze_model_responses(initial_responses, challenge_responses)
        
        # Step 5: Perform weighted aggregation
        print_colored("\nPerforming weighted aggregation...", "magenta")
        final_consensus = await weighted_aggregation(
            provider=provider,
            aggregator_config=settings.consensus_config.aggregator_config,
            model_responses=challenge_responses,
            analysis=analysis
        )
        
        # Display the final consensus result
        print_colored("\n" + "=" * 80, "green")
        print_colored("FINAL CONSENSUS RESULT".center(80), "green")
        print_colored("=" * 80 + "\n", "green")
        
        print(final_consensus)
        
        print_colored("\n" + "=" * 80, "green")
        
        # Save the results to a file
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        # Save the JSON result
        results_file = results_dir / "confident_consensus_result.json"
        with open(results_file, "w") as f:
            f.write(final_consensus)
        
        print_colored(f"\nSaved consensus result to {results_file}", "green")
        
    except Exception as e:
        print_colored(f"Error during consensus process: {e}", "red")
        import traceback
        traceback.print_exc()
    finally:
        # Close the provider's HTTP client
        await provider.close()


if __name__ == "__main__":
    # Import needed modules for statistics
    import statistics
    asyncio.run(main())