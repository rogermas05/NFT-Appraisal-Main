"""Improved aggregator with confidence-based weighting."""

import asyncio
import random
from typing import Dict, List

import structlog

from flare_ai_consensus.router import AsyncOpenRouterProvider, ChatRequest
from flare_ai_consensus.settings import AggregatorConfig

# Import from confidence package
from flare_ai_consensus.consensus.confidence.confidence_embeddings import (
    calculate_confidence_score, extract_price_and_explanation
)
from flare_ai_consensus.consensus.confidence.confidence_prompts import CHALLENGE_PROMPTS

logger = structlog.get_logger(__name__)


def _concatenate_weighted_aggregator(
    responses: Dict[str, str], 
    weights: Dict[str, float]
) -> str:
    """
    Aggregate responses with weights.

    Args:
        responses: A dictionary mapping model IDs to their response texts.
        weights: A dictionary mapping model IDs to their confidence scores.
    Returns:
        A single aggregated string with weight information.
    """
    weighted_responses = []
    for model_id, response in responses.items():
        weight = weights.get(model_id, 0.333)  # Default weight if not found
        price, _ = extract_price_and_explanation(response)
        
        # Include price and weight information
        weighted_responses.append(
            f"Model: {model_id} (Weight: {weight:.4f}, Price: ${price:.2f})\n{response}"
        )
    
    return "\n\n---\n\n".join(weighted_responses)


async def async_weighted_llm_aggregator(
    provider: AsyncOpenRouterProvider,
    aggregator_config: AggregatorConfig,
    model_responses: Dict[str, Dict[str, str]],
) -> str:
    """
    Use a weighted aggregation approach based on model confidence.
    
    Args:
        provider: An asynchronous OpenRouterProvider.
        aggregator_config: An instance of AggregatorConfig.
        model_responses: A dictionary with model responses from different iterations.
            Format: {model_id: {"initial": response, "final": response}}
    Returns:
        The aggregator's combined response as a string.
    """
    # Calculate confidence scores for each model
    confidence_scores = {}
    final_responses = {}
    
    logger.info("Calculating confidence scores for aggregation")
    
    for model_id, responses in model_responses.items():
        initial_response = responses.get("initial", "")
        final_response = responses.get("final", initial_response)
        
        # Store the final response for aggregation
        final_responses[model_id] = final_response
        
        # Calculate confidence score
        confidence_score = calculate_confidence_score(initial_response, final_response)
        confidence_scores[model_id] = confidence_score
        
        # Extract prices for logging
        initial_price, _ = extract_price_and_explanation(initial_response)
        final_price, _ = extract_price_and_explanation(final_response)
        
        logger.info(
            "model confidence analysis", 
            model_id=model_id,
            confidence_score=f"{confidence_score:.4f}",
            initial_price=f"${initial_price:.2f}",
            final_price=f"${final_price:.2f}"
        )
    
    # Normalize confidence scores to get weights
    total_confidence = sum(confidence_scores.values())
    if total_confidence > 0:
        weights = {
            model_id: score / total_confidence 
            for model_id, score in confidence_scores.items()
        }
    else:
        # Equal weights if all confidence scores are 0
        weight = 1.0 / len(confidence_scores)
        weights = {model_id: weight for model_id in confidence_scores}
    
    # Log the normalized weights
    for model_id, weight in weights.items():
        logger.info(
            "normalized weight", 
            model_id=model_id, 
            weight=f"{weight:.4f}"
        )
    
    # Create weighted aggregation for the meta-model
    weighted_responses = _concatenate_weighted_aggregator(final_responses, weights)
    
    # Build messages for the aggregator
    messages = []
    messages.extend(aggregator_config.context)
    
    # Create a system message with analysis of confidence and weights
    avg_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0
    
    system_message = {
        "role": "system", 
        "content": (
            f"Aggregated responses from multiple models with confidence-based weights:\n\n"
            f"Average confidence score: {avg_confidence:.4f}\n\n"
            f"{weighted_responses}"
        )
    }
    messages.append(system_message)
    
    # Create a special aggregator prompt that incorporates confidence information
    aggregator_prompt = {
        "role": "user",
        "content": (
            "You are synthesizing multiple NFT appraisals into a final estimate. "
            "Each model has been assigned a confidence weight based on how consistent "
            "their analysis remained when challenged. Models with higher weights showed "
            "greater confidence in their assessment.\n\n"
            "Your task is to create a final appraisal that:\n"
            "1. Puts more emphasis on models with higher confidence weights\n"
            "2. Starts with a clear price estimate (like '$X.XX USD')\n"
            "3. Incorporates the strongest reasoning from each model\n"
            "4. Acknowledges any significant disagreements\n"
            "5. Provides a comprehensive justification for the final price"
        )
    }
    messages.append(aggregator_prompt)
    
    # Send request to the aggregator model
    payload = ChatRequest(
        model=aggregator_config.model.model_id,
        messages=messages,
        max_tokens=aggregator_config.model.max_tokens,
        temperature=aggregator_config.model.temperature,
    )
    
    logger.info(
        "sending aggregation request", 
        aggregator_model=aggregator_config.model.model_id,
        num_models_aggregated=len(model_responses)
    )
    
    response = await provider.send_chat_completion(payload)
    aggregated_text = response.get("choices", [])[0].get("message", {}).get("content", "")
    
    # Extract price from aggregated response
    agg_price, _ = extract_price_and_explanation(aggregated_text)
    
    logger.info(
        "received aggregated response", 
        aggregator_model=aggregator_config.model.model_id,
        response_length=len(aggregated_text),
        aggregated_price=f"${agg_price:.2f}"
    )
    
    return aggregated_text


async def select_challenge_prompts(
    provider: AsyncOpenRouterProvider,
    model_responses: Dict[str, str],
    num_challenges: int = 1,
) -> Dict[str, List[str]]:
    """
    Select appropriate challenge prompts for each model based on their response.
    
    Args:
        provider: OpenRouter provider
        model_responses: Initial responses from each model
        num_challenges: Number of challenge prompts to select per model
    
    Returns:
        Dictionary mapping model_ids to lists of challenge prompts
    """
    # For simplicity in this implementation, randomly select challenges
    # In a more advanced version, we could analyze the model's response
    # and select the most relevant challenges
    
    challenges = {}
    for model_id in model_responses:
        # Randomly select challenge prompts
        model_challenges = random.sample(CHALLENGE_PROMPTS, min(num_challenges, len(CHALLENGE_PROMPTS)))
        challenges[model_id] = model_challenges
    
    return challenges