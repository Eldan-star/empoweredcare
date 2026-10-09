import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_available_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=api_key)

    print("🔍 Fetching available Gemini models...")
    try:
        print("\n✅ Models that can generate content (use these names in GEMINI_MODELS):")
        found_any = False
        for m in client.models.list():
            if "generateContent" in (m.supported_actions or []):
                found_any = True
                print(f"- {m.name.removeprefix('models/')}")

        if not found_any:
            print("No models found. Check your API key permissions.")

    except Exception as e:
        print(f"❌ Error listing models: {e}")

if __name__ == "__main__":
    list_available_models()
