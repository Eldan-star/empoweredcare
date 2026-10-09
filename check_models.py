import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- 🔍 Checking Available Models ---")
try:
    for m in client.models.list():
        if "generateContent" in (m.supported_actions or []):
            print(f"✅ Found Model: {m.name}")
except Exception as e:
    print(f"❌ Error listing models: {e}")
