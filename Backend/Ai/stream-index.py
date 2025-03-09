#!/usr/bin/env python3
import asyncio
import os
import json
import re
import random
import statistics
import time
from pathlib import Path
import textwrap
import aiohttp
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import queue
import threading

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.consensus import send_round
from flare_ai_consensus.consensus.aggregator import async_centralized_llm_aggregator
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json, parse_chat_response
from datetime import datetime

from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

load_dotenv()

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

# Parse data to compare accuracy
def accuracy_preparation(json_data):
    if json_data["sales_history"]:
        most_recent_transaction = json_data["sales_history"].pop(0)  # Removes and stores the first (latest) entry
        formatted_date = datetime.strptime(most_recent_transaction["date"], "%Y-%m-%d %H:%M:%S").strftime("%B, %Y")
    
    return most_recent_transaction["price_usd"], formatted_date, json_data


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
        
        # Format and wrap the response text
        wrapped_text = textwrap.fill(str(response), width=terminal_width-4)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        print_colored(f"{'-' * terminal_width}", "blue")
        
        # Store formatted response for streaming
        formatted_responses[model_id] = str(response)
    
    # Send detailed model responses as a stream event
    send_event("model_responses", {
        "title": title,
        "responses": formatted_responses
    })


def extract_price_from_text(text):
    """Extract the price from a response text or JSON string"""
    if not isinstance(text, str):
        if isinstance(text, dict) and "price" in text:
            return float(text["price"])
        elif isinstance(text, dict) and "predicted_price" in text:
            return float(text["predicted_price"])
        text = str(text)
        
    # First try to parse as JSON
    try:
        # Remove JSON code block markers if present
        if text.strip().startswith("```json"):
            text = re.sub(r'```json\s*|\s*```', '', text)
        
        # Try parsing the text as JSON
        data = json.loads(text)
        if isinstance(data, dict):
            if "price" in data:
                return float(data["price"])
            elif "predicted_price" in data:
                return float(data["predicted_price"])
            elif "predicted_price_USD" in data:
                return float(data["predicted_price_USD"])
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # If JSON parsing fails, try regular expression pattern matching
    try:
        # Look for "price": 1234.56 or "predicted_price": 1234.56
        price_match = re.search(r'"(?:price|predicted_price|predicted_price_USD)"\s*:\s*([0-9,]+\.?[0-9]*)', text)
        if price_match:
            return float(price_match.group(1).replace(',', ''))
        
        # Also try looking for dollar amounts
        dollar_match = re.search(r'\$([0-9,]+\.?[0-9]*)', text)
        if dollar_match:
            return float(dollar_match.group(1).replace(',', ''))
    except (ValueError, AttributeError):
        pass
    
    # Return None if no price was found
    return None


def calculate_confidence(std_dev, prices):
    """Calculate a confidence score based on standard deviation relative to mean"""
    if not prices or len(prices) < 2:
        return 0.5  # Default confidence with insufficient data
    
    mean_price = statistics.mean(prices)
    if mean_price == 0:
        return 0.5  # Avoid division by zero
    
    # Calculate coefficient of variation (normalized standard deviation)
    cv = std_dev / mean_price
    
    # Convert to confidence score (1 - normalized CV, bounded between 0.1 and 0.9)
    # Lower CV means higher confidence
    confidence = 1.0 - min(cv, 1.0)
    return max(0.1, min(0.9, confidence))


async def patch_provider_for_logging(provider):
    """Patch the provider's _post method to log request/response details"""
    original_post = provider._post
    
    async def logged_post(endpoint, json_payload):
        message = f"Request to {endpoint}: max_tokens={json_payload.get('max_tokens')}"
        print_colored(message, "blue")
        
        # Send model request event
        send_event("model_request", {
            "endpoint": endpoint,
            "max_tokens": json_payload.get('max_tokens'),
            "model": json_payload.get('model', 'unknown')
        })
        
        # Track start time for latency reporting
        start_time = time.time()
        response = await original_post(endpoint, json_payload)
        end_time = time.time()
        
        # Calculate latency in seconds
        latency = end_time - start_time
        
        # Send model response received event with latency
        send_event("model_response_received", {
            "model": json_payload.get('model', 'unknown'),
            "latency_seconds": latency
        })
        
        return response
    
    provider._post = logged_post
    return provider


async def run_consensus_with_data(
    provider, 
    consensus_config, 
    initial_conversation
):
    """
    Run consensus process and return both final result and all responses data.
    Modified version of the built-in run_consensus function to return all intermediate data.
    
    Args:
        provider: An instance of AsyncOpenRouterProvider
        consensus_config: Configuration for the consensus process
        initial_conversation: Initial prompt messages
        
    Returns:
        tuple: (final_consensus_result, all_response_data)
    """
    # Dictionary to store all responses and aggregations
    response_data = {}
    response_data["initial_conversation"] = initial_conversation

    # Step 1: Initial round
    print_colored("Running initial round of consensus...", "blue")
    send_event("stage", {"name": "initial_round", "description": "Querying models for initial predictions"})
    
    responses = await send_round(
        provider, consensus_config, response_data["initial_conversation"]
    )
    
    try:
        # Report to the stream that we're aggregating results
        send_event("stage", {"name": "aggregation", "description": "Aggregating initial model responses", "round": 0})
        
        aggregated_response = await async_centralized_llm_aggregator(
            provider, consensus_config.aggregator_config, responses
        )
        print_colored("Initial aggregation complete", "blue")
        
        # Send the aggregation result
        send_event("aggregation_complete", {
            "round": 0, 
            "response": str(aggregated_response)
        })
        
    except IndexError:
        # Handle the case where the aggregator fails to return a proper response
        print_colored("Error in aggregation: Empty response from aggregator model", "red")
        send_event("error", {
            "stage": "aggregation",
            "message": "Empty response from aggregator model", 
            "round": 0
        })
        
        # Create a fallback aggregated response by combining the most common elements
        prices = []
        explanations = []
        for model_id, response in responses.items():
            price = extract_price_from_text(response)
            if price is not None:
                prices.append(price)
            
            # Try to extract explanation
            try:
                if isinstance(response, str) and response.strip().startswith("```json"):
                    cleaned = re.sub(r'```json\s*|\s*```', '', response)
                    data = json.loads(cleaned)
                    if "explanation" in data:
                        explanations.append(data["explanation"])
            except:
                pass
        
        # Calculate average price if any prices were found
        avg_price = statistics.mean(prices) if prices else 0
        
        # Use the first explanation or a default one
        explanation = explanations[0] if explanations else "Unable to generate explanation due to aggregation error."
        
        # Create a simple JSON response
        aggregated_response = json.dumps({
            "price": avg_price,
            "explanation": explanation
        })
        print_colored(f"Created fallback aggregation with price: ${avg_price:.2f}", "yellow")
        
        # Send fallback aggregation event
        send_event("fallback_aggregation", {
            "price": avg_price,
            "explanation": explanation,
            "round": 0
        })

    response_data["iteration_0"] = responses
    response_data["aggregate_0"] = aggregated_response

    # Step 2: Improvement rounds
    for i in range(consensus_config.iterations):
        print_colored(f"Running improvement round {i+1}...", "blue")
        
        # Send improvement round start event
        send_event("stage", {
            "name": "improvement_round", 
            "round": i+1, 
            "description": f"Starting improvement round {i+1} of {consensus_config.iterations}"
        })
        
        responses = await send_round(
            provider, consensus_config, initial_conversation, aggregated_response
        )
        
        try:
            # Report aggregation stage
            send_event("stage", {
                "name": "aggregation", 
                "round": i+1, 
                "description": f"Aggregating responses from improvement round {i+1}"
            })
            
            aggregated_response = await async_centralized_llm_aggregator(
                provider, consensus_config.aggregator_config, responses
            )
            print_colored(f"Improvement round {i+1} complete", "blue")
            
            # Send aggregation result
            send_event("aggregation_complete", {
                "round": i+1, 
                "response": str(aggregated_response)
            })
            
        except IndexError:
            # Handle aggregation failure in improvement rounds
            print_colored(f"Error in improvement round {i+1} aggregation: Empty response from aggregator model", "red")
            send_event("error", {
                "stage": "aggregation",
                "message": "Empty response from aggregator model", 
                "round": i+1
            })
            
            # Keep the previous aggregated response
            print_colored("Using previous aggregation result", "yellow")
            send_event("fallback_aggregation", {
                "message": "Using previous aggregation result",
                "round": i+1
            })

        response_data[f"iteration_{i + 1}"] = responses
        response_data[f"aggregate_{i + 1}"] = aggregated_response

    # Return both the final consensus and all response data
    return aggregated_response, response_data


async def fetch_nft_data(contract_address: str, token_id: str):
    """Fetch NFT metadata from the API endpoint"""
    url = "https://get-nft-data-dkwdhhyv7q-uc.a.run.app"
    params = {
        "contract_address": contract_address,
        "token_id": token_id
    }
    
    print_colored(f"Fetching NFT data from API: {url}", "blue")
    send_event("stage", {"name": "fetch_metadata", "description": "Fetching NFT metadata from API"})
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                error_msg = f"API request failed with status {response.status}"
                print_colored(error_msg, "red")
                send_event("error", {"stage": "fetch_metadata", "message": error_msg})
                raise Exception(error_msg)
            
            data = await response.json()
            send_event("metadata_received", {"metadata": data})
            return data


async def fetch_ethereum_price():
    """Fetch current Ethereum price in USD from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "ethereum",
        "vs_currencies": "usd"
    }
    
    print_colored("Fetching Ethereum price from CoinGecko", "blue")
    send_event("stage", {"name": "fetch_eth_price", "description": "Fetching current Ethereum price in USD"})
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                error_msg = f"CoinGecko API request failed with status {response.status}"
                print_colored(error_msg, "red")
                send_event("error", {"stage": "fetch_eth_price", "message": error_msg})
                raise Exception(error_msg)
            
            data = await response.json()
            eth_price = data["ethereum"]["usd"]
            send_event("eth_price", {"price_usd": eth_price})
            return eth_price


async def process_nft_appraisal(contract_address: str, token_id: str):
    """Main processing function for NFT appraisal"""
    # Initialize variables that might be used in finally block
    provider = None
    
    try:
        print_colored("Fetching NFT data...", "blue")
        
        # Fetch NFT data
        metadata_data = await fetch_nft_data(contract_address, token_id)
        ACTUAL_VALUE, DATE_TO_PREDICT, metadata_data = accuracy_preparation(metadata_data)
        
        # Report the target date and actual value (hidden from user in real app)
        send_event("prediction_target", {
            "date": DATE_TO_PREDICT,
            "actual_value": ACTUAL_VALUE  # In real app, this would be unknown
        })
        
        print_colored("Preparing models...", "blue")
        send_event("stage", {"name": "preparation", "description": "Initializing consensus learning models"})
        
        # Load API key from environment variable
        api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
        if not api_key:
            error_msg = "Error: OPEN_ROUTER_API_KEY environment variable not set."
            print_colored(error_msg, "red")
            send_event("error", {"stage": "preparation", "message": error_msg})
            print("Please set your OpenRouter API key in your .env file")
            return None

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
        
        # Send configuration info to stream
        send_event("config", {
            "models": [model.model_id for model in settings.consensus_config.models],
            "aggregator": settings.consensus_config.aggregator_config.model.model_id,
            "iterations": settings.consensus_config.iterations
        })
        
        # Create the OpenRouter provider
        provider = AsyncOpenRouterProvider(
            api_key=api_key,
            base_url=settings.open_router_base_url
        )
        
        # Patch the provider for better logging
        provider = await patch_provider_for_logging(provider)
        
        content_prompt = """You are an expert at conducting NFT appraisals, and your goal is to output the price in USD value of the NFT at this specific date, which is $$$$$$. You will be given pricing history and other metadata about the NFT and will have to extrapolate and analyze the trends from the data. Your response MUST be in JSON format starting with a single value of price in USD, followed by a detailed explanation of your reasoning.

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
        
        # Define the NFT appraisal conversation
        nft_appraisal_conversation = [
            {
                "role": "system",
                "content": content_prompt.replace("$$$$$$", DATE_TO_PREDICT, 1)
                },
            {
                "role": "user",
                "content": f"Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers. Here is the sample data: {metadata_data}. "
            }
        ]
        
        # Send prompt info to stream
        send_event("prompt", {
            "system_prompt": content_prompt.replace("$$$$$$", DATE_TO_PREDICT, 1),
            "user_prompt": f"Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers. Here is the sample data: {json.dumps(metadata_data, default=str)}. "
        })
        
        print_colored("\nSending NFT appraisal request to multiple models...", "magenta")
        print_colored("Using sample data for NFT appraisal", "cyan")
        
        # Display configuration summary
        for model in settings.consensus_config.models:
            print_colored(f"Model: {model.model_id} (max_tokens: {model.max_tokens})", "yellow")
        
        aggregator_model = settings.consensus_config.aggregator_config.model
        print_colored(f"Aggregator: {aggregator_model.model_id} (max_tokens: {aggregator_model.max_tokens})", "yellow")
        
        try:
            # Step 1: Run the consensus process with data tracking
            print_colored("\nRunning consensus process...", "magenta")
            consensus_result, all_responses_data = await run_consensus_with_data(
                provider=provider,
                consensus_config=settings.consensus_config,
                initial_conversation=nft_appraisal_conversation
            )
            
            # Get the individual responses from the tracked data
            individual_responses = all_responses_data.get("iteration_0", {})
            
            # Display individual responses
            format_and_print_responses(individual_responses, "<INDIVIDUAL MODEL RESPONSES>")
            
            # Extract price estimates from individual responses
            initial_prices = {}
            for model_id, response in individual_responses.items():
                price = extract_price_from_text(response)
                if price is not None:
                    initial_prices[model_id] = price
                    print_colored(f"Extracted price from {model_id}: ${price:.2f}", "green")
            
            # Calculate initial price statistics
            initial_price_values = list(initial_prices.values())
            if initial_price_values:
                initial_mean_price = statistics.mean(initial_price_values)
                if len(initial_price_values) > 1:
                    initial_std_dev = statistics.stdev(initial_price_values)
                else:
                    initial_std_dev = 0
                initial_confidence_score = calculate_confidence(initial_std_dev, initial_price_values)
                
                print_colored(f"Initial Price statistics:", "magenta")
                print_colored(f"- Mean price: ${initial_mean_price:.2f}", "cyan")
                print_colored(f"- Standard deviation: ${initial_std_dev:.2f}", "cyan")
                print_colored(f"- Confidence score: {initial_confidence_score:.2f}", "cyan")
                
                # Send initial statistics to stream
                send_event("initial_statistics", {
                    "mean_price": initial_mean_price,
                    "std_dev": initial_std_dev,
                    "confidence_score": initial_confidence_score,
                    "model_prices": initial_prices
                })
            else:
                initial_mean_price = 0
                initial_std_dev = 0
                initial_confidence_score = 0
                print_colored("Warning: Could not extract any price estimates from model responses", "red")
                send_event("warning", {"message": "Could not extract any price estimates from model responses"})
            
            # Display the final consensus result
            print_colored("\n" + "=" * 80, "green")
            print_colored("FINAL CONSENSUS RESULT".center(80), "green")
            print_colored("=" * 80 + "\n", "green")
            
            # Format and wrap the consensus text
            wrapped_text = textwrap.fill(consensus_result, width=76)
            indented_text = textwrap.indent(wrapped_text, "  ")
            print(indented_text)
            
            print_colored("\n" + "=" * 80, "green")
            
            # Send final consensus result
            send_event("consensus_result", {"result": consensus_result})
            
            # Extract final price from consensus result
            final_consensus_price = extract_price_from_text(consensus_result)
            
            # Get final model responses from the last iteration of consensus
            final_iteration = settings.consensus_config.iterations
            if final_iteration > 0 and f"iteration_{final_iteration}" in all_responses_data:
                final_responses = all_responses_data[f"iteration_{final_iteration}"]
                print_colored(f"\nUsing responses from iteration {final_iteration} for statistics", "magenta")
                send_event("final_iteration", {"iteration": final_iteration})
            else:
                final_responses = individual_responses
                print_colored("\nUsing responses from initial round for statistics", "magenta")
                send_event("final_iteration", {"iteration": 0})
            
            # Display final model responses if different from initial
            if final_iteration > 0:
                format_and_print_responses(final_responses, "<FINAL MODEL RESPONSES>")
            
            # Extract price estimates from final responses
            final_prices = {}
            for model_id, response in final_responses.items():
                if response:  # Only process non-empty responses
                    price = extract_price_from_text(response)
                    if price is not None:
                        final_prices[model_id] = price
                        print_colored(f"Extracted final price from {model_id}: ${price:.2f}", "green")
            
            # Calculate final price statistics
            final_price_values = list(final_prices.values())
            if final_price_values:
                final_mean_price = statistics.mean(final_price_values)
                if len(final_price_values) > 1:
                    final_std_dev = statistics.stdev(final_price_values)
                else:
                    final_std_dev = 0
                final_confidence_score = calculate_confidence(final_std_dev, final_price_values)
                
                print_colored(f"Final Price statistics:", "magenta")
                print_colored(f"- Mean price: ${final_mean_price:.2f}", "cyan")
                print_colored(f"- Standard deviation: ${final_std_dev:.2f}", "cyan")
                print_colored(f"- Confidence score: {final_confidence_score:.2f}", "cyan")
                
                # Send final statistics to stream
                send_event("final_statistics", {
                    "mean_price": final_mean_price,
                    "std_dev": final_std_dev,
                    "confidence_score": final_confidence_score,
                    "model_prices": final_prices
                })
            else:
                # Fall back to initial statistics if no final prices
                final_mean_price = initial_mean_price
                final_std_dev = initial_std_dev
                final_confidence_score = initial_confidence_score
                print_colored("Warning: Could not extract prices from final responses, using initial statistics", "yellow")
                send_event("warning", {"message": "Could not extract prices from final responses, using initial statistics"})
            
            # If consensus price is None, use mean price
            if final_consensus_price is None:
                final_consensus_price = final_mean_price
                print_colored("Warning: Could not extract price from consensus result, using mean price", "yellow")
                send_event("warning", {"message": "Could not extract price from consensus result, using mean price"})
            
            # Clean up consensus result if it's a JSON string with JSON markdown
            cleaned_result = consensus_result
            if isinstance(consensus_result, str) and consensus_result.strip().startswith("```json"):
                cleaned_result = re.sub(r'```json\s*|\s*```', '', consensus_result)
            
            # Try to parse the result as JSON
            try:
                result_json = json.loads(cleaned_result)
                explanation = result_json.get("explanation", "")
                if not explanation and "predicted_price_USD" in result_json:
                    # Try alternative fields
                    explanation = result_json.get("text", "")
            except json.JSONDecodeError:
                explanation = cleaned_result
                print_colored("Warning: Could not parse consensus result as JSON", "yellow")
                send_event("warning", {"message": "Could not parse consensus result as JSON"})
            except Exception as e:
                explanation = cleaned_result
                print_colored(f"Warning: Error parsing consensus result: {str(e)}", "yellow")
                send_event("warning", {"message": f"Error parsing consensus result: {str(e)}"})
            
            # Before creating final output JSON, get ETH price
            try:
                eth_price = await fetch_ethereum_price()
            except Exception as e:
                print_colored(f"Warning: Could not fetch ETH price: {e}", "yellow")
                send_event("warning", {"message": f"Could not fetch ETH price: {e}"})
                eth_price = 0
                
            # Create final output JSON
            final_output = {
                "price": final_consensus_price,
                "text": explanation,
                "standard_deviation": final_std_dev,
                "total_confidence": final_confidence_score,
                "ethereum_price_usd":  final_consensus_price / eth_price if eth_price > 0 else 0,
            }
            
            error_accuracy = abs(final_output["price"] - ACTUAL_VALUE) / ACTUAL_VALUE 
            if 1 - error_accuracy < 0:
                accuracy = 0
            else:
                accuracy = 1 - error_accuracy
            
            final_output["accuracy"] = accuracy
            
            print(f"Accuracy: {accuracy}")
            print(f"Actual Value: {ACTUAL_VALUE}")
            print(f"Predicted Value: {final_output['price']}")
            
            # Send accuracy metrics to stream
            send_event("accuracy_metrics", {
                "accuracy": accuracy,
                "actual_value": ACTUAL_VALUE,
                "predicted_value": final_output['price']
            })
            
            # Send final result completion event
            send_event("stage", {"name": "complete", "description": "Consensus learning process completed"})
            
            # Convert to JSON string
            final_json_string = json.dumps(final_output, indent=2)
            
            # Print final JSON
            print_colored("\nFINAL JSON OUTPUT:", "magenta")
            print(final_json_string)
            
            # Send complete results to stream
            send_event("final_result", final_output)
            
            # Save the results to a file
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)
            
            results_file = results_dir / "latest_consensus_result.json"
            with open(results_file, "w") as f:
                f.write(final_json_string)
            
            print_colored(f"\nSaved consensus result to {results_file}", "green")
            
            # Return the final JSON string
            return final_json_string
        
        except Exception as e:
            print()
            
    except Exception as e:
        error_msg = f"Error during consensus process: {e}"
        print_colored(error_msg, "red")
        send_event("error", {"stage": "consensus", "message": str(e)})
        import traceback
        traceback.print_exc()
        return json.dumps({
            "price": 0,
            "text": error_msg,
            "standard_deviation": 0,
            "total_confidence": 0
        })
    finally:
        # Send process end event
        send_event("process_end", {"timestamp": datetime.now().isoformat()})
        # Close the provider's HTTP client if it exists
        if provider:
            try:
                await provider.close()
            except Exception as e:
                print_colored(f"Error closing provider: {e}", "yellow")



# Generator function for SSE streaming
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
            
            # If this is the final stage event with "complete" status, close the connection
            if event_type == "stage" and event.get("data", {}).get("name") == "complete":
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


# Flask route for streaming API
@app.route('/appraise/stream', methods=['GET'])
def appraise_nft_stream_api():
    """Streaming API endpoint to appraise an NFT with real-time updates"""
    # Clear the event queue for a fresh start
    while not event_queue.empty():
        event_queue.get()
    
    # Get parameters from the request
    contract_address = request.args.get('contract_address')
    token_id = request.args.get('token_id')
    
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
        asyncio.run(process_nft_appraisal(contract_address, token_id))
    
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


# Flask route for the standard API (non-streaming)
@app.route('/appraise', methods=['GET'])
def appraise_nft_api():
    """API endpoint to appraise an NFT"""
    try:
        # Get parameters from the request
        contract_address = request.args.get('contract_address')
        token_id = request.args.get('token_id')
        
        if not contract_address or not token_id:
            return jsonify({
                "error": "Missing contract_address or token_id parameter",
                "price": 0,
                "text": "Error: Missing required parameters",
                "standard_deviation": 0,
                "total_confidence": 0
            }), 400
        
        # Run the async processing in a new event loop
        result_json = asyncio.run(process_nft_appraisal(contract_address, token_id))
        
        # Parse the result back to a dictionary
        result = json.loads(result_json)
        
        # Return the result
        return jsonify(result)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "price": 0,
            "text": f"Error during consensus process: {str(e)}",
            "standard_deviation": 0,
            "total_confidence": 0
        }), 500

# Command-line interface
if __name__ == "__main__":
    import sys
    
    # Check if running in API mode or CLI mode
    if len(sys.argv) > 1 and sys.argv[1] == "--api":
        # Run as API server
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        print_colored(f"Starting API server on port {port}...", "green")
        app.run(host='0.0.0.0', port=port, threaded=True)
    elif len(sys.argv) == 3:
        # Run as CLI
        contract_address = sys.argv[1]
        token_id = sys.argv[2]
        result = asyncio.run(process_nft_appraisal(contract_address, token_id))
        print_colored("\nProgram completed.", "green")
    else:
        print("Usage:")
        print("  python cloud_index.py <contract_address> <token_id>  # Run as CLI")
        print("  python cloud_index.py --api [port]                  # Run as API server")