#!/usr/bin/env python3
import asyncio
import os
import json
import random
from pathlib import Path
import textwrap

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.consensus import run_consensus, send_round
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json

from sample import sample_data
from dotenv import load_dotenv


load_dotenv()


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
        wrapped_text = textwrap.fill(response, width=terminal_width-4)
        indented_text = textwrap.indent(wrapped_text, "  ")
        print(indented_text)
        print_colored(f"{'-' * terminal_width}", "blue")


async def patch_provider_for_logging(provider):
    """Patch the provider's _post method to log request/response details"""
    original_post = provider._post
    
    async def logged_post(endpoint, json_payload):
        print_colored(f"Request to {endpoint}: max_tokens={json_payload.get('max_tokens')}", "blue")
        response = await original_post(endpoint, json_payload)
        return response
    
    provider._post = logged_post
    return provider


async def main():
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
    
    appraisal_date = "March, 2025"
        
    # if not config_file.exists():
    if True:
        default_config = {
            "models": [
        {
            "id": "meta-llama/llama-3.2-3b-instruct:free",
            "max_tokens": 3500,
            "temperature": 0.7
        },
        {
            "id": "google/gemini-2.0-flash-001",
            "max_tokens": 3500,
            "temperature": 0.7
        },
        
        {
            "id": "perplexity/sonar-reasoning",
            "max_tokens": 3500,
            "temperature": 0.7
        }
    ],
            "aggregator": [
                {
                    "model": {
                        "id": "google/gemini-flash-1.5-8b-exp",
                        "max_tokens": 3500,
                        "temperature": 0.65
                    },
                    "aggregator_context": [
                        {
                            "role": "system",
                            "content": "Your role is to objectively evaluate responses from multiple large-language models and combine them into a single coherent response. Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers. Focus on accuracy and completeness in your synthesis."
                        }
                    ],
                    "aggregator_prompt": [
                        {
                            "role": "user",
                            "content": """You have been provided with responses from various models to the latest query. Synthesize these responses into a single, high-quality answer. If the models disagree on any point, note this and explain the different perspectives. Your response should be well-structured, comprehensive, and accurate. Your response should be in JSON format like the models, and start with a SINGLE VALUE USD prediction of the NFT Price. Then there will be an explanation component where you will conduct your thorough discussion. Ensure that you are following the JSON format.
                            """
                        }
                    ]
                }
            ],
            "aggregated_prompt_type": "system",
            "improvement_prompt": "Please provide an improved answer based on the consensus responses. Your entire response/output is going to consist of a single JSON object, and you will NOT wrap it within JSON md markers",
            "iterations": 1
        }
        
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=4)
        
        print_colored(f"Created default configuration file at {config_file}", "green")
    
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
        # Step 1: Get individual model responses
        print_colored("\nGetting individual model responses...", "magenta")
        individual_responses = await send_round(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=nft_appraisal_conversation
        )
        
        # Display individual responses
        format_and_print_responses(individual_responses, "<INDIVIDUAL MODEL RESPONSES>")
        
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
        
        # Save the results to a file
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / "latest_consensus_result.txt"
        with open(results_file, "w") as f:
            f.write(consensus_result)
        
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