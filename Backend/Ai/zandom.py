from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
result = client.models.embed_content(
        model="text-embedding-004",
        contents="What is the meaning of life?")

print(result.embeddings)