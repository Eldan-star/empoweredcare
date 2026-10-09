import os
import time
import PIL.Image
from google import genai
from google.genai import errors as genai_errors
import json
import io
from pathlib import Path
from dotenv import load_dotenv
from models.schemas import StructuredMedicalRecord, Medication
from config import GEMINI_MODEL_PREFERENCES

load_dotenv()

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GEMINI_API_KEY not found in .env file")
        
        self.client = genai.Client(api_key=self.api_key)

        # Tried in order; set GEMINI_MODELS in .env when Google retires a model.
        self.models = GEMINI_MODEL_PREFERENCES

    def _generate(self, model_name: str, contents) -> str:
        """One generate_content call; returns the reply text or raises."""
        response = self.client.models.generate_content(model=model_name, contents=contents)
        if not response.text:
            raise ValueError("Empty response")
        return response.text

    @staticmethod
    def _is_rate_limit(e: Exception) -> bool:
        return (isinstance(e, genai_errors.APIError) and e.code == 429) or "429" in str(e)

    def process_medical_record(self, image_path) -> StructuredMedicalRecord:
        img = PIL.Image.open(image_path)
        prompt = """
        You are a Universal Medical Intelligence Agent. Analyze this medical document (Handwritten or Printed) with 100% precision.
        
        GOAL: 
        1. Identify the TYPE of document (e.g. Prescription, Lab Report, Referral, Chart).
        2. Detect all handwritten and printed text in any language detected.
        3. Extract the 'CORE entities': Patient Identity, Date, and Clinical Narrative.
        4. Capture ALL specific medical details (Diagnosis, Medications, Tests, Symptoms).
        
        DYNAMIC STRUCTURING:
        If the form has unique headers or fields that do not fit the common schema, capture them exactly as key-value pairs in 'additional_info'.
        
        Return a single JSON object ONLY:
        {
          "document_type": "Autodetected type",
          "patient_name": "...",
          "patient_id": "...",
          "date_of_birth": "...",
          "gender": "...",
          "visit_date": "Original date on document",
          "referred_from": "...",
          "referred_to": "...",
          "diagnosis": ["..."],
          "symptoms": ["..."],
          "investigations": ["..."],
          "medications": [{"name": "...", "dosage": "...", "frequency": "..."}],
          "allergies": [],
          "notes": "Concise professional summary",
          "additional_info": {
            "AUTO_DETECTED_FIELD": "Handwritten/Printed Value"
          },
          "confidence": 1.0
        }
        """

        last_error = None
        for model_name in self.models:
            for attempt in range(2): # Try to retry if rate limit is encountered
                try:
                    print(f"🧠 Universal Scan: Using {model_name}...")
                    raw_text = self._generate(model_name, [prompt, img])
                    
                    print(f"\n📂 UNIVERSAL VISION RESULT:\n{raw_text}\n--------------------------\n")

                    if "```json" in raw_text:
                        json_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        json_text = raw_text.split("```")[1].split("```")[0].strip()
                    else:
                        json_text = raw_text.strip()
                    
                    data = json.loads(json_text)
                    
                    return StructuredMedicalRecord(
                        document_type=data.get("document_type", "Medical Record"),
                        patient_name=data.get("patient_name", "Unknown"),
                        patient_id=data.get("patient_id"),
                        date_of_birth=data.get("date_of_birth"),
                        gender=data.get("gender"),
                        visit_date=data.get("visit_date"),
                        referred_from=data.get("referred_from"),
                        referred_to=data.get("referred_to"),
                        diagnosis=data.get("diagnosis", []),
                        symptoms=data.get("symptoms", []),
                        investigations=data.get("investigations", []),
                        medications=[Medication(**m) for m in data.get("medications", [])],
                        allergies=data.get("allergies", []),
                        notes=data.get("notes", ""),
                        additional_info=data.get("additional_info", {}),
                        confidence=float(data.get("confidence", 0.99))
                    )

                except Exception as e:
                    print(f"⚠️ {model_name} Error (Attempt {attempt+1}): {e}")
                    last_error = e
                    if self._is_rate_limit(e):
                        print("⏳ 429 Rate limit encountered. Pausing for 35 seconds...")
                        time.sleep(35)
                    else:
                        break # Stop trying with the current model for non-rate-limit errors
            continue # Attempt the next model in the list
            
        raise ValueError(f"❌ Gemini failed with all models: {last_error}")

    def generate_text(self, prompt: str) -> str:
        """Generate text response using Gemini for text-only prompts."""
        last_error = None
        for model_name in self.models:
            for attempt in range(2):
                try:
                    print(f"🧠 Text Generation: Using {model_name}...")
                    raw_text = self._generate(model_name, prompt)
                    
                    if "```json" in raw_text:
                        json_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        json_text = raw_text.split("```")[1].split("```")[0].strip()
                    else:
                        json_text = raw_text.strip()
                    
                    return json_text
                    
                except Exception as e:
                    print(f"⚠️ {model_name} Error (Attempt {attempt+1}): {e}")
                    last_error = e
                    if self._is_rate_limit(e):
                        print("⏳ 429 Rate limit encountered. Pausing for 35 seconds...")
                        time.sleep(35)
                    else:
                        break
            continue
            
        raise ValueError(f"❌ Gemini text generation failed: {last_error}")

    def generate_vision_text(self, image_path_or_bytes, prompt: str) -> str:
        """Extract text from an image using Gemini Vision."""
        if isinstance(image_path_or_bytes, (str, Path)):
            img = PIL.Image.open(image_path_or_bytes)
        else:
            img = PIL.Image.open(io.BytesIO(image_path_or_bytes))
            
        last_error = None
        for model_name in self.models:
            for attempt in range(2):
                try:
                    print(f"🧠 Vision Scan: Using {model_name}...")
                    raw_text = self._generate(model_name, [prompt, img])
                    
                    return raw_text.strip()
                    
                except Exception as e:
                    print(f"⚠️ {model_name} Vision Error (Attempt {attempt+1}): {e}")
                    last_error = e
                    if self._is_rate_limit(e):
                        print("⏳ 429 Rate limit encountered. Pausing for 35 seconds...")
                        time.sleep(35)
                    else:
                        break
            continue
            
        raise ValueError(f"❌ Gemini Vision failed: {last_error}")