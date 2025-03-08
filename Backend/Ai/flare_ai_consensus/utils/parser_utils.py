def parse_chat_response(response: dict) -> str:
    """Parse response from chat completion endpoint"""
    choices = response.get("choices", [])
    if not choices:
        # Log the full response to help with debugging
        import json
        print(f"Warning: Received empty choices list. Full response: {json.dumps(response, indent=2)}")
        return ""  # Return empty string instead of raising an exception
        
    return choices[0].get("message", {}).get("content", "")


def extract_author(model_id: str) -> tuple[str, str]:
    """
    Extract the author and slug from a model_id.

    :param model_id: The model ID string.
    :return: A tuple (author, slug).
    """
    author, slug = model_id.split("/", 1)
    return author, slug
