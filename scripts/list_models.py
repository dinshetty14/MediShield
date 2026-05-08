"""List available Gemini models."""
import sys
sys.path.insert(0, ".")

from google import genai
from app.config import get_settings

settings = get_settings()
client = genai.Client(api_key=settings.effective_gemini_key)

print("Available models:")
for model in client.models.list():
    print(f"  - {model.name}")
