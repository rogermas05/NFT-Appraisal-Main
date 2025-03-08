"""Confidence-based consensus with challenge prompts."""

import asyncio
import random
from typing import Dict, List, Tuple, Optional

import structlog

from flare_ai_consensus.router import AsyncOpenRouterProvider, ChatRequest
from flare_ai_consensus.settings import ConsensusConfig, Message, ModelConfig
from flare_ai_consensus.utils import parse_chat_response

# Import from confidence package
from flare_ai_consensus.consensus.confidence.confidence_aggregator import (
    async_weighted_llm_aggregator, select_challenge_prompts
)
from flare_ai_consensus.consensus.confidence.confidence_prompts import CHALLENGE_PROMPTS

logger = structlog.get_logger(__name__)


async def run_confident_consensus(
    provider: AsyncOpenRouterProvider,
    consensus_config: ConsensusConfig,
    initial_conversation: List[Message],
    num_challenges: int = 3,  # Number of challenge iterations
) -> str:
    """
    Run the confidence-based consensus process with challenge rounds.
    
    Args:
        provider: An instance of an AsyncOpenRouterProvider
        consensus_config: Configuration for the consensus process
        initial_conversation: The input user prompt with system instructions
        num_challenges: Number of challenge rounds to run
        
    Returns:
        Final aggregated response
    """
    # Store all responses from different iterations
    all_model_responses = {}
    
    # Step 1: Get initial responses from all models
    logger.info("Getting initial responses from models")
    initial_responses = await send_round(
        provider, consensus_config, initial_conversation
    )
    
    # Initialize the all_model_responses dictionary
    for model_id, response in initial_responses.items():
        all_model_responses[model_id] = {"initial": response}
    
    # Step 2: Run challenge rounds
    for i in range(num_challenges):
        logger.info(f"Running challenge round {i+1}/{num_challenges}")
        
        # Select challenge prompts for each model
        challenges = await select_challenge_prompts(
            provider, initial_responses, num_challenges=1
        )
        
        # Send challenges to models
        challenge_responses = await send_challenge_round(
            provider, 
            consensus_config, 
            initial_conversation,
            challenges
        )
        
        # Store the final response from the challenge rounds
        for model_id, response in challenge_responses.items():
            all_model_responses[model_id][f"challenge_{i+1}"] = response
            # Update the "final" response with the latest response
            all_model_responses[model_id]["final"] = response
    
    # Step 3: Create weighted aggregation based on confidence
    logger.info("Creating weighted aggregation based on confidence")
    aggregated_response = await async_weighted_llm_aggregator(
        provider, consensus_config.aggregator_config, all_model_responses
    )
    
    return aggregated_response


def _build_challenge_conversation(
    initial_conversation: List[Message],
    challenge_prompt: str,
) -> List[Message]:
    """
    Build a conversation that includes a challenge prompt.
    
    Args:
        initial_conversation: Original conversation
        challenge_prompt: The challenge prompt to add
        
    Returns:
        Updated conversation with challenge
    """
    conversation = initial_conversation.copy()
    
    # Add challenge prompt as user message
    conversation.append(
        {"role": "user", "content": challenge_prompt}
    )
    
    return conversation


async def _get_response_for_model_with_challenge(
    provider: AsyncOpenRouterProvider,
    model: ModelConfig,
    initial_conversation: List[Message],
    challenge_prompt: str,
) -> Tuple[str, str]:
    """
    Get a response from a model with a challenge prompt.
    
    Args:
        provider: OpenRouter provider
        model: Model configuration
        initial_conversation: Original conversation
        challenge_prompt: Challenge prompt to add
        
    Returns:
        Tuple of (model_id, response)
    """
    # Build conversation with challenge
    conversation = _build_challenge_conversation(
        initial_conversation, challenge_prompt
    )
    
    logger.info(
        "sending challenge prompt", 
        model_id=model.model_id,
        challenge=challenge_prompt[:50] + "..." if len(challenge_prompt) > 50 else challenge_prompt
    )
    
    # Send request to model
    payload = ChatRequest(
        model=model.model_id,
        messages=conversation,
        max_tokens=model.max_tokens,
        temperature=model.temperature,
    )
    
    response = await provider.send_chat_completion(payload)
    text = parse_chat_response(response)
    
    logger.info(
        "received challenge response", 
        model_id=model.model_id,
        response_length=len(text)
    )
    
    return model.model_id, text


async def send_challenge_round(
    provider: AsyncOpenRouterProvider,
    consensus_config: ConsensusConfig,
    initial_conversation: List[Message],
    model_challenges: Dict[str, List[str]],
) -> Dict[str, str]:
    """
    Send challenge prompts to all models and get their responses.
    
    Args:
        provider: OpenRouter provider
        consensus_config: Consensus configuration
        initial_conversation: Original conversation
        model_challenges: Dictionary mapping model IDs to challenge prompts
        
    Returns:
        Dictionary mapping model IDs to their responses
    """
    tasks = []
    
    for model in consensus_config.models:
        # Get challenge prompt for this model
        model_id = model.model_id
        challenges = model_challenges.get(model_id, [])
        
        if not challenges:
            # If no specific challenge, use a random one
            challenge = random.choice(CHALLENGE_PROMPTS)
        else:
            challenge = challenges[0]  # Use the first challenge in the list
        
        # Create task for getting response
        task = _get_response_for_model_with_challenge(
            provider, model, initial_conversation, challenge
        )
        tasks.append(task)
    
    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)
    
    # Convert results to dictionary
    return dict(results)


async def send_round(
    provider: AsyncOpenRouterProvider,
    consensus_config: ConsensusConfig,
    initial_conversation: List[Message],
    aggregated_response: Optional[str] = None,
) -> Dict[str, str]:
    """
    Send initial conversation to all models and get their responses.
    
    This is similar to the original send_round but simplified to only support
    the initial round without aggregated responses.
    
    Args:
        provider: OpenRouter provider
        consensus_config: Consensus configuration
        initial_conversation: Original conversation
        aggregated_response: Not used in this implementation
        
    Returns:
        Dictionary mapping model IDs to their responses
    """
    tasks = []
    
    for model in consensus_config.models:
        logger.info("sending initial prompt", model_id=model.model_id)
        
        # Create request payload
        payload = ChatRequest(
            model=model.model_id,
            messages=initial_conversation,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
        )
        
        # Define coroutine to get response
        async def get_response(model_id, payload):
            response = await provider.send_chat_completion(payload)
            text = parse_chat_response(response)
            logger.info("received initial response", model_id=model_id)
            return model_id, text
        
        # Create task
        task = get_response(model.model_id, payload)
        tasks.append(task)
    
    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)
    
    # Convert results to dictionary
    return dict(results)