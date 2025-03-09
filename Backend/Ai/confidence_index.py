#!/usr/bin/env python3
import asyncio
import os
import json
from pathlib import Path
import textwrap
import time
import structlog

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json

# Import our custom confidence consensus components
from flare_ai_consensus.consensus.confidence import (
    run_confident_consensus,
    send_round,
    extract_price_and_explanation
)
from flare_ai_consensus.consensus.confidence.confidence_embeddings import calculate_text_similarity

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
        
        # Extract price from response
        try:
            price, _ = extract_price_and_explanation(response_text)
            if price > 0:
                print(f"Estimated price: ${price:.2f}")
        except Exception as e:
            print(f"Error extracting price: {e}")
        
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


# Add a function to log similarity scores
def log_similarity_details(initial_response, final_response):
    """Log detailed information about response similarity"""
    from flare_ai_consensus.consensus.confidence.confidence_embeddings import extract_price_and_explanation
    
    initial_price, initial_explanation = extract_price_and_explanation(initial_response)
    final_price, final_explanation = extract_price_and_explanation(final_response)
    
    # Calculate price change
    if initial_price == 0 and final_price == 0:
        price_change = 0
    elif initial_price == 0:
        price_change = 1
    else:
        price_change = abs(final_price - initial_price) / initial_price
    
    # Calculate text similarity
    text_similarity = calculate_text_similarity(initial_explanation, final_explanation)
    
    logger.info(
        "Response comparison",
        initial_price=f"${initial_price:.2f}",
        final_price=f"${final_price:.2f}",
        price_change_pct=f"{price_change*100:.2f}%",
        text_similarity=f"{text_similarity:.4f}"
    )
    
    print_colored(f"Initial price: ${initial_price:.2f}", "cyan")
    print_colored(f"Final price: ${final_price:.2f}", "cyan")
    print_colored(f"Price change: {price_change*100:.2f}%", "magenta")
    print_colored(f"Text similarity: {text_similarity:.4f}", "magenta")


async def main():
    # Handle command line arguments
    import sys
    
    # Default number of challenge rounds
    num_challenges = 3
    
    # Check if challenge rounds specified
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        num_challenges = int(sys.argv[1])
        print_colored(f"Using {num_challenges} challenge rounds", "yellow")
    
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
        initial_responses = await send_round(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation
        )
        
        # Display individual responses
        format_and_print_responses(initial_responses, "<INITIAL MODEL RESPONSES>")
        logger.info("Initial responses collected", model_count=len(initial_responses))
        
        time.sleep(3)
        
        # Step 2: Run the confidence-based consensus with challenge rounds
        print_colored(f"\nRunning confidence-based consensus with {num_challenges} challenge rounds...", "magenta")
        logger.info("Starting challenge rounds", num_challenges=num_challenges)
        
        # Store all responses for logging
        all_responses = {model_id: {"initial": response} for model_id, response in initial_responses.items()}
        format_and_print_responses(all_responses, "<ITERATED MODEL RESPONSES>")
        
        # Run challenge rounds and collect responses
        final_consensus = await run_confident_consensus(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation,
            num_challenges=num_challenges,
            response_collector=all_responses  # Pass the collector to store responses
        )
        
        # Log similarity details for each model
        print_colored("\nResponse stability analysis:", "blue")
        logger.info("Analyzing response stability")
        for model_id, responses in all_responses.items():
            print_colored(f"\nModel: {model_id}", "yellow")
            initial = responses.get("initial", "")
            final = responses.get(f"challenge_{num_challenges}", "") or responses.get("final", initial)
            log_similarity_details(initial, final)
        
        # Display the final consensus result
        print_colored("\n" + "=" * 80, "green")
        print_colored("FINAL CONSENSUS RESULT".center(80), "green")
        print_colored("=" * 80 + "\n", "green")
        
        # Extract price from final consensus
        price, explanation = extract_price_and_explanation(final_consensus)
        if price > 0:
            print_colored(f"Final estimated price: ${price:.2f}", "green")
        
        # Format and wrap the consensus text
        wrapped_text = textwrap.fill(final_consensus, width=76)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        
        print_colored("\n" + "=" * 80, "green")
        
        # Save the results to a file
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / "confident_consensus_result.txt"
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
    asyncio.run(main())