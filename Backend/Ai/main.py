

#!/usr/bin/env python3
import asyncio
import os
import json
from pathlib import Path

from flare_ai_consensus.router import AsyncOpenRouterProvider
from flare_ai_consensus.consensus import run_consensus
from flare_ai_consensus.settings import Settings, Message
from flare_ai_consensus.utils import load_json
from prompt import sample_data
from dotenv import load_dotenv


load_dotenv()


async def main():
    # Load API key from environment variable
    api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        print("Please set your OpenRouter API key: export OPENROUTER_API_KEY=your_api_key")
        return

    # Initialize the settings
    settings = Settings()
    
    # Create a path to store configuration (could be in the current directory)
    config_path = Path("config")
    config_path.mkdir(exist_ok=True)
    
    # Load the consensus configuration
    config_file = config_path / "consensus_config.json"
    
    # If the config file doesn't exist, create it with default settings
    if not config_file.exists():
        default_config = {
            "models": [
                {
                    "id": "meta-llama/llama-3.2-3b-instruct:free",
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                {
                    "id": "qwen/qwen-vl-plus:free",
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                {
                    "id": "sophosympatheia/rogue-rose-103b-v0.2:free",
                    "max_tokens": 200,
                    "temperature": 0.7
                }
            ],
            "aggregator": [
                {
                    "model": {
                        "id": "meta-llama/llama-3.2-3b-instruct:free",
                        "max_tokens": 200,
                        "temperature": 0.7
                    },
                    "aggregator_context": [
                        {
                            "role": "system",
                            "content": "Your role is to objectively evaluate responses from multiple large-language models and combine them into a single coherent response."
                        }
                    ],
                    "aggregator_prompt": [
                        {
                            "role": "user",
                            "content": "You have been provided with responses from various models to the latest query. Synthesize these responses into a single, high-quality answer. Ensure your response is well-structured and accurately represents the mathematical solution."
                        }
                    ]
                }
            ],
            "aggregated_prompt_type": "system",
            "improvement_prompt": "Please provide an improved answer based on the consensus responses.",
            "iterations": 2
        }
        
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=4)
        
        print(f"Created default configuration file at {config_file}")
    
    # Load the configuration
    config_json = load_json(config_file)
    settings.load_consensus_config(config_json)
    
    # Create the OpenRouter provider
    provider = AsyncOpenRouterProvider(
        api_key=api_key,
        base_url=settings.open_router_base_url
    )
    
    # Define a conversation
    problem_conversation = [
        {
            "role": "system",
            "content": "You are an expert at conducting NFT appraisals, and you goal is to output the price the USD value of the NFT at this current date, which is March, 2025. You will be given pricing history and other metadata about the NFT and will have to extrapolate and analyze the trends from the data. Your response start with the price in USD, followed by a detailed explanation of your reasoning."
        },
        {
            "role": "user",
            "content": f"Here is the sample data: {sample_data}"
        }
    ]
    
    print("Sending the problem to multiple models...")
    print(f"Question: {problem_conversation[1]['content']}\n")
    
    # Run the consensus process
    try:
        result = await run_consensus(
            provider=provider,
            consensus_config=settings.consensus_config,
            initial_conversation=problem_conversation
        )
        
        print("\n=== CONSENSUS RESULT ===\n")
        print(result)
        print("\n=======================\n")
        
    except Exception as e:
        print(f"Error during consensus process: {e}")
    finally:
        # Close the provider's HTTP client
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())