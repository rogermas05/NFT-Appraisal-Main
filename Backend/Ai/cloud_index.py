#!/usr/bin/env python3
import asyncio
import os
import json
import re
import random
import statistics
from pathlib import Path
import textwrap

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.consensus import run_consensus, send_round
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json, parse_chat_response
from datetime import datetime

from sample import sample_data
from dotenv import load_dotenv


load_dotenv()

ACCURACY_METRIC_DESIRED = True

# Parse data to compare accuracy
def accuracy_preparation(json_data):
    if json_data["sales_history"]:
        most_recent_transaction = json_data["sales_history"].pop(0)  # Removes and stores the first (latest) entry
        formatted_date = datetime.strptime(most_recent_transaction["date"], "%Y-%m-%d %H:%M:%S").strftime("%B, %Y")
    
    return most_recent_transaction["price_usd"], formatted_date, json_data

if ACCURACY_METRIC_DESIRED:
    ACTUAL_VALUE, DATE_TO_PREDICT, sample_data = accuracy_preparation(sample_data)


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
    
    print_colored(f"\n{separator}", "cyan")
    print_colored(f"{title.center(terminal_width)}", "cyan")
    print_colored(f"{separator}\n", "cyan")
    
    for model_id, response in responses.items():
        print_colored(f"Model: {model_id}", "yellow")
        
        # Format and wrap the response text
        wrapped_text = textwrap.fill(str(response), width=terminal_width-4)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        print_colored(f"{'-' * terminal_width}", "blue")


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
        print_colored(f"Request to {endpoint}: max_tokens={json_payload.get('max_tokens')}", "blue")
        response = await original_post(endpoint, json_payload)
        return response
    
    provider._post = logged_post
    return provider


async def get_final_responses(provider, consensus_config, initial_conversation, aggregated_response):
    """Get final responses from all models after seeing the consensus"""
    improved_responses = {}
    
    # Build the improvement conversation
    conversation = initial_conversation.copy()
    
    # Add aggregated response
    conversation.append({
        "role": consensus_config.aggregated_prompt_type,
        "content": f"Consensus: {aggregated_response}",
    })
    
    # Add new prompt as "user" message
    conversation.append({
        "role": "user", 
        "content": consensus_config.improvement_prompt,
    })
    
    # Request from each model
    for model in consensus_config.models:
        try:
            # Create payload
            payload = {
                "model": model.model_id,
                "messages": conversation,
                "max_tokens": model.max_tokens,
                "temperature": model.temperature,
            }
            
            # Get response
            response = await provider.send_chat_completion(payload)
            text = parse_chat_response(response)
            improved_responses[model.model_id] = text
            print_colored(f"Received improved response from {model.model_id}", "green")
            
        except Exception as e:
            print_colored(f"Error getting improved response from {model.model_id}: {e}", "red")
    
    return improved_responses


async def main():
    # Load API key from environment variable
    api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    if not api_key:
        print_colored("Error: OPEN_ROUTER_API_KEY environment variable not set.", "red")
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
        # Step 1: Get individual model responses
        print_colored("\nGetting individual model responses...", "magenta")
        individual_responses = await send_round(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation
        )
        
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
        else:
            initial_mean_price = 0
            initial_std_dev = 0
            initial_confidence_score = 0
            print_colored("Warning: Could not extract any price estimates from model responses", "red")
        
        # Step 2: Run the single consensus process
        print_colored("\nRunning consensus aggregation...", "magenta")
        consensus_result = await run_consensus(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation
        )
        
        # Display the final consensus result
        print_colored("\n" + "=" * 80, "green")
        print_colored("FINAL CONSENSUS RESULT".center(80), "green")
        print_colored("=" * 80 + "\n", "green")
        
        # Format and wrap the consensus text
        wrapped_text = textwrap.fill(consensus_result, width=76)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        
        print_colored("\n" + "=" * 80, "green")
        
        # Extract final price from consensus result
        final_consensus_price = extract_price_from_text(consensus_result)
        
        # Get final model responses after seeing the consensus
        print_colored("\nGetting final model responses after consensus...", "magenta")
        final_responses = await get_final_responses(
            provider, 
            settings.consensus_config,
            nft_appraisal_conversation,
            consensus_result
        )
        
        # Display final model responses
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
        else:
            # Fall back to initial statistics if no final prices
            final_mean_price = initial_mean_price
            final_std_dev = initial_std_dev
            final_confidence_score = initial_confidence_score
            print_colored("Warning: Could not extract prices from final responses, using initial statistics", "yellow")
        
        # If consensus price is None, use mean price
        if final_consensus_price is None:
            final_consensus_price = final_mean_price
            print_colored("Warning: Could not extract price from consensus result, using mean price", "yellow")
        
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
        
        # Create final output JSON
        final_output = {
            "price": final_consensus_price,
            "text": explanation,
            "standard_deviation": final_std_dev,
            "total_confidence": final_confidence_score
        }
        
        error_accuracy = abs(final_output["price"] - ACTUAL_VALUE) / ACTUAL_VALUE 
        accuracy = 1 - error_accuracy
        final_output["accuracy"] = accuracy
        print(f"Accuracy: {accuracy}")
        print(f"Actual Value: {ACTUAL_VALUE}")
        print(f"Predicted Value: {final_output['price']}")
        
        # Convert to JSON string
        final_json_string = json.dumps(final_output, indent=2)
        
        # Print final JSON
        print_colored("\nFINAL JSON OUTPUT:", "magenta")
        print(final_json_string)
        
        
        # Change this if you want file in results folder
        want_file = True
        
        if want_file:
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
        print_colored(f"Error during consensus process: {e}", "red")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "price": 0,
            "text": f"Error during consensus process: {str(e)}",
            "standard_deviation": 0,
            "total_confidence": 0
        })
    finally:
        # Close the provider's HTTP client
        await provider.close()


if __name__ == "__main__":
    result = asyncio.run(main())
    print_colored("\nProgram completed.", "green")