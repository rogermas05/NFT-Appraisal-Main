#!/usr/bin/env python3
import asyncio
import os
import json
import re
import statistics
from pathlib import Path
import textwrap
import aiohttp
from flask import Flask, request, jsonify
from flask_cors import CORS

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json
from datetime import datetime

from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

load_dotenv()


# Parse data to compare accuracy
def accuracy_preparation(json_data):
    if json_data["sales_history"]:
        most_recent_transaction = json_data["sales_history"].pop(0)  # Removes and stores the first (latest) entry
        formatted_date = datetime.strptime(most_recent_transaction["date"], "%Y-%m-%d %H:%M:%S").strftime("%B, %Y")
    
    return most_recent_transaction["price_usd"], formatted_date, json_data


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


def extract_confidence_from_text(text):
    """Extract the confidence level from a response text or JSON string"""
    if not isinstance(text, str):
        if isinstance(text, dict) and "confidence" in text:
            return float(text["confidence"])
        text = str(text)
        
    # First try to parse as JSON
    try:
        # Remove JSON code block markers if present
        if text.strip().startswith("```json"):
            text = re.sub(r'```json\s*|\s*```', '', text)
        
        # Try parsing the text as JSON
        data = json.loads(text)
        if isinstance(data, dict) and "confidence" in data:
            # Convert from 0-100 to 0-1 if needed
            confidence = float(data["confidence"])
            return confidence / 100 if confidence > 1 else confidence
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    
    # If JSON parsing fails, try regular expression pattern matching
    try:
        # Look for "confidence": 0.85 or "confidence": 85
        confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', text)
        if confidence_match:
            confidence = float(confidence_match.group(1))
            return confidence / 100 if confidence > 1 else confidence
        
        # Also try looking for confidence percentages
        percent_match = re.search(r'confidence.*?([0-9.]+)%', text, re.IGNORECASE)
        if percent_match:
            return float(percent_match.group(1)) / 100
    except (ValueError, AttributeError):
        pass
    
    # Return None if no confidence was found
    return None


async def patch_provider_for_logging(provider):
    """Patch the provider's _post method to log request/response details"""
    original_post = provider._post
    
    async def logged_post(endpoint, json_payload):
        print_colored(f"Request to {endpoint}: max_tokens={json_payload.get('max_tokens')}", "blue")
        response = await original_post(endpoint, json_payload)
        return response
    
    provider._post = logged_post
    return provider


async def fetch_nft_data(contract_address: str, token_id: str):
    """Fetch NFT metadata using the main function from sideinfo.py"""
    # Import the main function from sideinfo.py
    import sys
    import os
    
    # Get the current file's directory and add parent directories to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(current_dir))
    
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    
    # Now import using relative path
    from Backend.Ai.Sideinfo_api.sideinfo import main
    
    # Call the main function directly
    return main(contract_address, token_id)


async def fetch_ethereum_price():
    """Fetch current Ethereum price in USD from CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "ethereum",
        "vs_currencies": "usd"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API request failed with status {response.status}")
            data = await response.json()
            return data["ethereum"]["usd"]


async def query_single_llm(provider, model_id, messages, max_tokens=2000):
    """Query a single LLM model for NFT appraisal"""
    print_colored(f"Sending request to model: {model_id}", "blue")
    
    try:
        # Create payload based on the consensus.py send_round function
        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7  # Default temperature
        }
        
        # Use the correct method from consensus.py
        response = await provider.send_chat_completion(payload)
        
        # Use the parse_chat_response function if it's accessible
        try:
            from flare_ai_consensus.utils import parse_chat_response
            return parse_chat_response(response)
        except ImportError:
            # Fallback if parse_chat_response isn't available
            if response and "choices" in response:
                return response["choices"][0]["message"]["content"]
            else:
                print_colored(f"Error: Unexpected response format from {model_id}", "red")
                return None
    except Exception as e:
        print_colored(f"Error querying {model_id}: {e}", "red")
        return None


async def process_nft_appraisal(contract_address: str, token_id: str):
    """Main processing function for NFT appraisal using a single LLM"""
    # Initialize provider variable outside try block for finally clause
    provider = None
    
    try:
        print_colored("Fetching NFT data...", "blue")
        
        # Fetch NFT data
        metadata_data = await fetch_nft_data(contract_address, token_id)
        ACTUAL_VALUE, DATE_TO_PREDICT, metadata_data = accuracy_preparation(metadata_data)
        
        print_colored("Preparing model...", "blue")
        
        # Load API key from environment variable
        api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
        if not api_key:
            print_colored("Error: OPEN_ROUTER_API_KEY environment variable not set.", "red")
            print("Please set your OpenRouter API key in your .env file")
            return None

        # Create the OpenRouter provider
        provider = AsyncOpenRouterProvider(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Patch the provider for better logging
        provider = await patch_provider_for_logging(provider)
        
        # Use Llama model as default
        model_id = "google/gemini-2.0-flash-001"
        max_tokens = 2000
        
        content_prompt = """You are an expert at conducting NFT appraisals, and your goal is to output the price in USD value of the NFT at this specific date, which is $$$$$$. You will be given pricing history and other metadata about the NFT and will have to extrapolate and analyze the trends from the data. 

            Your response MUST be in JSON format with the following properties:
            1. "price" - Your predicted price in USD as a number
            2. "explanation" - A detailed but concise explanation of your reasoning. Do not exceed three sentences at all costs, and try to focus on different NFT features like rarirty, past sales data, and also context about the NFT.
            3. "confidence" - Your confidence level in this prediction as a decimal between 0 and 1 (e.g., 0.85 for 85% confidence)

            Do NOT wrap your JSON response in markdown code blocks.

            In the given data, the price of Ethereum (price_ethereum) was how much Ethereum was paid at the time and the price in USD (price_usd) is the price of that Ethereum at the time of the sale in USD. 

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
                "explanation": "Based on the sales history, the price of the NFT has been increasing over time. The most recent sale was for 24.61 ETH, which is worth $61914.7812 at the time of the sale. The previous sale was for 85 ETH, which is worth $108403.25579 at the time of the sale. Based on this data, I estimate that the price of the NFT is currently $67240. Additional context on the rarity would help improve the response and the price estimate.",
                "confidence": 0.75
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
                "content": f"Please provide an NFT appraisal in JSON format with price, explanation, and your confidence level. Here is the sample data: {metadata_data}"
            }
        ]
        
        print_colored(f"\nSending NFT appraisal request to {model_id}...", "magenta")
        print_colored("Using sample data for NFT appraisal", "cyan")
        
        # Query the LLM
        response = await query_single_llm(
            provider=provider,
            model_id=model_id,
            messages=nft_appraisal_conversation,
            max_tokens=max_tokens
        )
        
        if not response:
            raise Exception("Failed to get a response from the model")
        
        # Display the raw model response
        print_colored("\n" + "=" * 80, "cyan")
        print_colored("MODEL RESPONSE".center(80), "cyan")
        print_colored("=" * 80 + "\n", "cyan")
        
        # Format and wrap the response text
        wrapped_text = textwrap.fill(response, width=76)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        
        print_colored("\n" + "=" * 80, "cyan")
        
        # Extract the price and confidence from the response
        price = extract_price_from_text(response)
        confidence = extract_confidence_from_text(response)
        
        if price is not None:
            print_colored(f"Extracted price: ${price:.2f}", "green")
        else:
            print_colored("Warning: Could not extract price from model response", "yellow")
            price = 0
            
        if confidence is not None:
            print_colored(f"Extracted confidence: {confidence:.2f}", "green")
        else:
            print_colored("Warning: Could not extract confidence from model response", "yellow")
            confidence = 0.5  # Default to 50% confidence
        
        # Clean up response if it's a JSON string with JSON markdown
        cleaned_result = response
        if isinstance(response, str) and response.strip().startswith("```json"):
            cleaned_result = re.sub(r'```json\s*|\s*```', '', response)
        
        # Try to parse the result as JSON
        try:
            result_json = json.loads(cleaned_result)
            explanation = result_json.get("explanation", "")
            if not explanation and "text" in result_json:
                explanation = result_json.get("text", "")
        except json.JSONDecodeError:
            explanation = cleaned_result
            print_colored("Warning: Could not parse model response as JSON", "yellow")
        
        # Before creating final output JSON, get ETH price
        try:
            eth_price = await fetch_ethereum_price()
        except Exception as e:
            print_colored(f"Warning: Could not fetch ETH price: {e}", "yellow")
            eth_price = 0
            
        # Calculate accuracy based on actual value
        error_accuracy = abs(price - ACTUAL_VALUE) / ACTUAL_VALUE if ACTUAL_VALUE > 0 else 1.0
        if 1 - error_accuracy < 0:
            accuracy = 0
        else:
            accuracy = 1 - error_accuracy
        
        # Create final output JSON
        final_output = {
            "price": price,
            "text": explanation,
            "confidence": confidence,
            "accuracy": accuracy,
            "ethereum_price_usd": price / eth_price if eth_price > 0 else 0
        }
        
        print(f"Accuracy: {accuracy}")
        print(f"Actual Value: {ACTUAL_VALUE}")
        print(f"Predicted Value: {price}")
        
        # Convert to JSON string
        final_json_string = json.dumps(final_output, indent=2)
        
        # Print final JSON
        print_colored("\nFINAL JSON OUTPUT:", "magenta")
        print(final_json_string)
        
        # Save the results to a file
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / "latest_single_result.json"
        with open(results_file, "w") as f:
            f.write(final_json_string)
        
        print_colored(f"\nSaved result to {results_file}", "green")
        
        # Return the final JSON string
        return final_json_string
        
    except Exception as e:
        print_colored(f"Error during NFT appraisal: {e}", "red")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "price": 0,
            "text": f"Error during NFT appraisal: {str(e)}",
            "confidence": 0,
            "accuracy": 0
        })
    finally:
        # Close the provider's HTTP client if it exists
        if provider:
            try:
                await provider.close()
            except Exception as e:
                print_colored(f"Error closing provider: {e}", "yellow")


# Flask route for the API
@app.route('/single_llm_appraisal', methods=['GET'])
def appraise_nft_api():
    """API endpoint to appraise an NFT using a single LLM"""
    try:
        # Get parameters from the request
        contract_address = request.args.get('contract_address')
        token_id = request.args.get('token_id')
        
        if not contract_address or not token_id:
            return jsonify({
                "error": "Missing contract_address or token_id parameter",
                "price": 0,
                "text": "Error: Missing required parameters",
                "confidence": 0,
                "accuracy": 0
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
            "text": f"Error during NFT appraisal: {str(e)}",
            "confidence": 0,
            "accuracy": 0
        }), 500


# Command-line interface
if __name__ == "__main__":
    import sys
    
    # Check if running in API mode or CLI mode
    if len(sys.argv) > 1 and sys.argv[1] == "--api":
        # Run as API server
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        print_colored(f"Starting API server on port {port}...", "green")
        app.run(host='0.0.0.0', port=8083)
    elif len(sys.argv) == 3:
        # Run as CLI
        contract_address = sys.argv[1]
        token_id = sys.argv[2]
        result = asyncio.run(process_nft_appraisal(contract_address, token_id))
        print_colored("\nProgram completed.", "green")
    else:
        print("Usage:")
        print("  python cloud_single.py <contract_address> <token_id>  # Run as CLI")
        print("  python cloud_single.py --api [port]                   # Run as API server")