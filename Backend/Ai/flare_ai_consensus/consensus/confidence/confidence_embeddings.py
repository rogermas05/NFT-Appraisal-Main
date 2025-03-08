"""Utility functions for embedding-based similarity using Gemini model."""

import re
import os
import numpy as np
from typing import Tuple
import importlib.util
import structlog

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Gemini's API
gemini_available = False

try:
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        gemini_available = True
except ImportError:
    pass

logger = structlog.get_logger(__name__)

def get_embeddings(text: str) -> np.ndarray:
    """
    Get embeddings for a text using Gemini's embedding model.
    
    Args:
        text: Text to embed
        
    Returns:
        numpy.ndarray: Embedding vector
    """
    if not gemini_available:
        logger.warning("Gemini API not available, using fallback embedding method")
        # Fallback to a simple approach if Gemini API is not available
        # This creates a simplistic frequency-based vector
        words = text.lower().split()
        unique_words = list(set(words))
        embedding = np.zeros(len(unique_words))
        for i, word in enumerate(unique_words):
            embedding[i] = words.count(word) / len(words)
        return embedding
    
    try:
        # Use Gemini's text embedding model
        logger.info("Getting embeddings from Gemini API", text_length=len(text))
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        # Convert the ContentEmbedding object to a numpy array
        # The values are stored in the 'values' field of the embedding
        values = result.embeddings[0].values
        logger.info("Received embeddings from Gemini API", embedding_size=len(values))
        return np.array(values)
    except Exception as e:
        logger.error("Error getting embeddings from Gemini API", error=str(e))
        # Fallback to simple approach
        words = text.lower().split()
        unique_words = list(set(words))
        embedding = np.zeros(len(unique_words))
        for i, word in enumerate(unique_words):
            embedding[i] = words.count(word) / len(words)
        return embedding


def extract_price_and_explanation(text: str) -> Tuple[float, str]:
    """
    Extract the price estimate and explanation from a model response.
    
    Args:
        text: Full response text from a model
        
    Returns:
        tuple: (price_estimate, explanation_text)
    """
    # Try to extract a dollar amount from the beginning of the text
    price_match = re.search(r'^\$?([0-9,]+\.?[0-9]*)', text.strip())
    price = None
    if price_match:
        try:
            price = float(price_match.group(1).replace(',', ''))
            logger.debug("Extracted price from beginning of text", price=price)
        except ValueError:
            pass
    
    # If no price found at the beginning, try a more general search
    if price is None:
        price_patterns = [
            r'\$([0-9,]+\.?[0-9]*)',  # $123.45
            r'([0-9,]+\.?[0-9]*)\s*USD',  # 123.45 USD
            r'([0-9,]+\.?[0-9]*)\s*dollars',  # 123.45 dollars
            r'price[^\$]*\$([0-9,]+\.?[0-9]*)',  # price is $123.45
            r'value[^\$]*\$([0-9,]+\.?[0-9]*)',  # value is $123.45
            r'estimate[^\$]*\$([0-9,]+\.?[0-9]*)',  # estimate is $123.45
            r'worth[^\$]*\$([0-9,]+\.?[0-9]*)',  # worth is $123.45
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, text, re.IGNORECASE)
            if price_match:
                try:
                    price = float(price_match.group(1).replace(',', ''))
                    logger.debug("Extracted price using pattern", pattern=pattern, price=price)
                    break
                except ValueError:
                    continue
    
    # Default to 0 if no price found
    if price is None:
        logger.warning("No price found in text", text_preview=text[:100] + "..." if len(text) > 100 else text)
        price = 0.0
    
    # For explanation, remove the price declaration from the beginning if it exists
    if price_match and price_match.start() == 0:
        explanation = text[price_match.end():].strip()
    else:
        explanation = text.strip()
    
    return price, explanation


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate the cosine similarity between two texts using Gemini embeddings.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        float: Cosine similarity score (0-1)
    """
    logger.info("Calculating text similarity", text1_length=len(text1), text2_length=len(text2))
    
    # Get embeddings
    embedding1 = get_embeddings(text1)
    embedding2 = get_embeddings(text2)
    
    # Ensure embeddings are 1D arrays
    if hasattr(embedding1, 'shape') and len(embedding1.shape) > 1:
        embedding1 = embedding1.flatten()
    if hasattr(embedding2, 'shape') and len(embedding2.shape) > 1:
        embedding2 = embedding2.flatten()
    
    # Ensure dimensions match for fallback method
    if hasattr(embedding1, 'shape') and hasattr(embedding2, 'shape') and embedding1.shape != embedding2.shape:
        logger.warning("Embedding dimensions don't match", 
                      dim1=embedding1.shape, dim2=embedding2.shape)
        min_dim = min(embedding1.shape[0], embedding2.shape[0])
        embedding1 = embedding1[:min_dim]
        embedding2 = embedding2[:min_dim]
    
    # Calculate cosine similarity
    try:
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            logger.warning("Zero norm in embeddings", norm1=norm1, norm2=norm2)
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure value is in [0, 1] range
        similarity_value = max(0.0, min(float(similarity), 1.0))
        logger.info("Calculated similarity", similarity=similarity_value)
        return similarity_value
    except TypeError as e:
        logger.error("Error calculating similarity", error=str(e))
        # If vectors can't be compared, return 0.5 as a neutral similarity
        return 0.5


def calculate_confidence_score(initial_response: str, final_response: str) -> float:
    """
    Calculate a confidence score based on how much a model changes its response.
    
    Args:
        initial_response: The model's initial response
        final_response: The model's response after challenges
        
    Returns:
        float: Confidence score (0-1), where higher means less change (more confidence)
    """
    logger.info("Calculating confidence score")
    
    initial_price, initial_explanation = extract_price_and_explanation(initial_response)
    final_price, final_explanation = extract_price_and_explanation(final_response)
    
    # Calculate price change percentage
    if initial_price == 0 and final_price == 0:
        price_change = 0
        logger.info("Both prices are zero, no price change")
    elif initial_price == 0:
        price_change = 1  # Maximum change if initial price was 0
        logger.info("Initial price was zero, maximum price change")
    else:
        price_change = min(abs(final_price - initial_price) / initial_price, 1)
        logger.info("Price change calculated", 
                   initial_price=initial_price, 
                   final_price=final_price, 
                   change_pct=f"{price_change*100:.2f}%")
    
    # Calculate text similarity
    text_similarity = calculate_text_similarity(initial_explanation, final_explanation)
    logger.info("Text similarity calculated", similarity=text_similarity)
    
    # Calculate confidence score (inverse of change)
    confidence_score = 1 - (0.5 * price_change + 0.5 * (1 - text_similarity))
    logger.info("Confidence score calculated", 
               price_factor=0.5 * price_change,
               similarity_factor=0.5 * (1 - text_similarity),
               confidence_score=confidence_score)
    
    return confidence_score