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
        
    if not config_file.exists():
        # Fall back to default configuration if free_models.json isn't available
        default_config = {
            "models": [
                {
                    "id": "meta-llama/llama-3.2-3b-instruct:free",
                    "max_tokens": 3500,
                    "temperature": 0.7
                },
                {
                    "id": "qwen/qwen-vl-plus:free",
                    "max_tokens": 3500,
                    "temperature": 0.7
                },
                {
                    "id": "deepseek/deepseek-chat:free",
                    "max_tokens": 3500,
                    "temperature": 0.7
                }
            ],
            "aggregator": [
                {
                    "model": {
                        "id": "meta-llama/llama-3.2-3b-instruct:free",
                        "max_tokens": 3500,
                        "temperature": 0.5
                    },
                    "aggregator_context": [
                        {
                            "role": "system",
                            "content": "Your role is to objectively evaluate responses from multiple large-language models and combine them into a single coherent response. Focus on accuracy and completeness in your synthesis."
                        }
                    ],
                    "aggregator_prompt": [
                        {
                            "role": "user",
                            "content": "You have been provided with responses from various models to the latest query. Synthesize these responses into a single, high-quality answer. If the models disagree on any point, note this and explain the different perspectives. Your response should be well-structured, comprehensive, and accurate."
                        }
                    ]
                }
            ],
            "aggregated_prompt_type": "system",
            "improvement_prompt": "Please provide an improved answer based on the consensus responses.",
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
    nft_appraisal_conversation = [
        {
            "role": "system",
            "content": """You are an expert at conducting NFT appraisals, and your goal is to output the price in USD value of the NFT at this current date, which is March, 2025. You will be given pricing history and other metadata about the NFT and will have to extrapolate and analyze the trends from the data. Your response start with the price in USD, followed by a detailed explanation of your reasoning.
            The sample data that you will be given will be in this input format, although the values will be different. Use it to understand how the data is laid out and what each entry means, but the actual values are fake so don't learn from them.
            In the json, the price of ethereum (price_ethereum) was how much ethereum was paid at the time and the price in usd (price_usd) is the price of that ethereum at the time of the sale in USD. 
            {
                "name": "World Of Women",
                "token_id": "4267",
                "token_address": "0xe785e82358879f061bc3dcac6f0444462d4b5330",
                "metadata": {
                    "symbol": "WOW",
                    "rarity_rank": 6665,
                    "rarity_percentage": 66.65,
                    "amount": "1"
                },
                "sales_history": [
                    {
                        "price_ethereum": 0.37,
                        "price_usd": 804.02931,
                        "date": "2025-03-05 14:42:35"
                    },
                    {
                        "price_ethereum": 0.338,
                        "price_usd": 900.05486,
                        "date": "2024-02-17 23:20:47"
                    },
                    {
                        "price_ethereum": 0.339,
                        "price_usd": 928.88703,
                        "date": "2023-02-17 23:19:59"
                    },
                    {
                        "price_ethereum": 0.353,
                        "price_usd": 939.99812,
                        "date": "2022-02-14 19:02:11"
                    }
                ]
            }            
            
            """
        },
        {
            "role": "user",
            "content": f"Here is the sample data: {sample_data}"
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