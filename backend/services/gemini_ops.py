"""Gemini AI operations service for carbon footprint estimation and eco-coaching."""
import json
import logging
import re
import unicodedata
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.carbon_calc import calculate_footprint

logger = logging.getLogger(__name__)

# Try importing the new Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Try importing Groq SDK (fallback LLM provider)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

def _sanitize_text(text: str) -> str:
    """Remove BOM characters and other invisible Unicode that break API calls."""
    if not text:
        return text
    # Strip BOM (\ufeff) and other zero-width chars
    text = text.replace('\ufeff', '').replace('\ufffe', '')
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    return text.strip()


def _extract_bold_key(text: str) -> str:
    """Safely extract the first **bold** keyword from a string for deduplication.
    Returns the bold content lowercased, or the first 40 chars of the string if no bold markers exist."""
    parts = text.split("**")
    if len(parts) >= 2:
        return parts[1].lower()
    return text[:40].lower()


class GeminiService:
    # Use the latest model that works with google-genai SDK
    MODEL_FLASH = 'gemini-2.0-flash'
    MODEL_PRO = 'gemini-2.0-flash'  # Use flash for all — fast + capable
    MODEL_EMBEDDING = 'text-embedding-004'
    
    # Groq fallback model (fast Llama inference)
    GROQ_MODEL = 'llama-3.3-70b-versatile'

    def __init__(self):
        self.client = None         # Gemini client
        self.groq_client = None    # Groq fallback client
        self.mock_mode = settings.USE_MOCK_SERVICES
        self.using_groq = False    # Track which provider is active
        
        # Priority 1: Try Gemini
        if not self.mock_mode and GENAI_AVAILABLE and (settings.GEMINI_API_KEY or settings.ENV == "production"):
            try:
                api_key = _sanitize_text(settings.GEMINI_API_KEY)
                http_options = types.HttpOptions(timeout=10000)  # 10s timeout
                if api_key:
                    self.client = genai.Client(api_key=api_key, http_options=http_options)
                else:
                    self.client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location="us-central1", http_options=http_options)
                logger.info("Gemini client initialized. Model: %s", self.MODEL_FLASH)
            except Exception as e:
                logger.warning("Gemini init failed: %s", e)
                self.client = None
        
        # Priority 2: Try Groq as fallback
        if self.client is None and not self.mock_mode and GROQ_AVAILABLE and settings.GROQ_API_KEY:
            try:
                groq_key = _sanitize_text(settings.GROQ_API_KEY)
                self.groq_client = Groq(api_key=groq_key, timeout=10.0)  # 10s timeout
                self.using_groq = True
                logger.info("Groq fallback initialized. Model: %s", self.GROQ_MODEL)
            except Exception as e:
                logger.warning("Groq init failed: %s", e)
                self.groq_client = None
        
        # If neither provider is available, enter mock mode
        if self.client is None and self.groq_client is None:
            self.mock_mode = True
            if not settings.USE_MOCK_SERVICES:
                logger.warning("No LLM provider available. Running in mock mode. "
                               "Set GEMINI_API_KEY or GROQ_API_KEY in your .env file.")

    # --- GROQ FALLBACK HELPERS ---
    
    def _groq_generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 800) -> Optional[str]:
        """Generate text using Groq API. Returns None on failure."""
        if not self.groq_client:
            return None
        try:
            response = self.groq_client.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Groq API error: %s", e)
            return None
    
    def _groq_generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Optional[Any]:
        """Generate JSON using Groq API with json_object response format. Returns parsed JSON or None."""
        if not self.groq_client:
            return None
        try:
            response = self.groq_client.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            return json.loads(raw)
        except Exception as e:
            logger.error("Groq JSON API error: %s", e)
            return None

    # --- MAIN API METHODS ---

    def parse_natural_language_log(self, text: str) -> List[Dict[str, Any]]:
        """
        Parses unstructured natural language into structured carbon logs.
        Priority: Gemini → Groq → Mock fallback.
        """
        if self.mock_mode:
            return self._mock_parse_natural_language(text)

        prompt = f"""
        You are a carbon footprint estimation assistant. Parse the following user text and extract ALL carbon-relevant activities.
        User text: "{text}"

        For each activity, output a structured JSON array of objects with the following keys:
        - "category": Must be one of ["transit", "energy", "food", "waste"]
        - "subcategory": Use specific names. Examples:
            * transit: "car_petrol", "car_diesel", "car_electric", "motorbike", "bus", "train", "flight_economy", "flight_business"
            * energy: "electricity_kwh", "natural_gas_m3", "lpg_kg"
            * food: "beef_kg", "pork_kg", "poultry_kg", "fish_kg", "dairy_kg", "meal_vegan", "meal_vegetarian", "meal_meat_heavy", "meal_standard"
            * waste: "landfill_kg", "recycled_kg"
        - "quantity": The numerical amount (e.g. km driven, meals eaten, kg of meat, kWh used). Estimate a standard default if not explicitly mentioned (e.g. 1 meal, 15 km drive).
        - "unit": The unit of measurement (e.g., "km", "kWh", "meals", "kg")
        - "description": A short friendly description of what was done (e.g., "Ate beef burgers", "Flew economy flight Delhi to Mumbai")

        Output strictly JSON. Return only the JSON list of activities.
        """
        
        activities = None
        
        # Try Gemini first
        if self.client:
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL_PRO,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                activities = json.loads(response.text.strip())
            except Exception as e:
                logger.error("Gemini parse_log failed: %s", e)
        
        # Try Groq fallback
        if activities is None and self.groq_client:
            system = "You are a carbon footprint estimation assistant. Always respond with valid JSON only — a JSON array of activity objects."
            result = self._groq_generate_json(system, prompt)
            if result is not None:
                # Groq json_object mode wraps in an object — handle both list and {"activities": [...]}
                if isinstance(result, list):
                    activities = result
                elif isinstance(result, dict):
                    activities = result.get("activities", result.get("items", [result]))
        
        # If we got activities from either provider, enrich with carbon calculations
        if activities:
            for activity in activities:
                calc = calculate_footprint(
                    activity.get("category", "food"),
                    activity.get("subcategory", "meal_standard"),
                    float(activity.get("quantity", 1))
                )
                activity["carbon_kg"] = calc["carbon_kg"]
                activity["explanation"] = calc["calculation_basis"]
            return activities
        
        # Final fallback to mock
        logger.warning("All LLM providers failed for parse_log. Using mock parser.")
        return self._mock_parse_natural_language(text)

    def parse_receipt(self, file_bytes: bytes, file_mime: str) -> Dict[str, Any]:
        """
        Parses receipt or utility bill using Gemini Flash multimodal capabilities.
        Note: Groq doesn't support multimodal — falls back to mock for receipt OCR.
        """
        if self.mock_mode or self.using_groq:
            return self._mock_parse_receipt(file_mime)

        prompt = """
        You are an expert OCR receipt and bill parser specializing in environmental impact analysis.
        Analyze this image or document. Extract the following information in JSON format:
        {
          "merchant": "Name of store, utility company, or restaurant",
          "date": "YYYY-MM-DD or null if not found",
          "total_amount": 0.0,
          "is_utility_bill": true/false (true if electricity, gas, water, fuel bill; false if supermarket/restaurant),
          "items": [
             {
               "name": "Item name or utility consumption name (e.g., Electricity Consumption)",
               "quantity": 1.0,
               "price": 0.0,
               "carbon_category": "transit", "energy", "food", "waste" or "other",
               "carbon_subcategory": "electricity_kwh", "beef_kg", "car_petrol", etc.,
               "units": "kWh", "kg", "meals", etc.
             }
          ]
        }
        For utility bills, identify the consumption quantities (e.g. kWh of electricity, m3 of gas).
        For groceries/restaurants, identify major carbon-intensive foods (beef, cheese, poultry, pork, fish).
        Output ONLY the raw JSON format.
        """
        try:
            # Prepare multimodal part
            contents = [
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=file_mime
                ),
                prompt
            ]
            response = self.client.models.generate_content(
                model=self.MODEL_FLASH,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            parsed = json.loads(response.text.strip())
            
            # Enrich items with carbon calculation
            total_carbon = 0.0
            for item in parsed.get("items", []):
                cat = item.get("carbon_category", "other")
                sub = item.get("carbon_subcategory", "")
                qty = float(item.get("quantity", 1))
                
                # Check if it has a valid carbon category
                if cat != "other" and sub:
                    calc = calculate_footprint(cat, sub, qty)
                    item["carbon_kg"] = calc["carbon_kg"]
                    total_carbon += calc["carbon_kg"]
                else:
                    item["carbon_kg"] = 0.0
            
            parsed["estimated_total_carbon_kg"] = round(total_carbon, 2)
            return parsed
        except Exception as e:
            logger.error("Error parsing receipt with Gemini Flash: %s. Falling back to mock receipt OCR.", e)
            return self._mock_parse_receipt(file_mime)

    def generate_coaching_response(self, message: str, chat_history: List[Dict[str, str]], tips: List[str], current_score_kg: float) -> str:
        """
        Generates conversational eco-coaching responses utilizing injected RAG tips.
        Uses a comprehensive system prompt to be culturally aware, context-sensitive,
        and give genuinely helpful sustainability advice.
        """
        if self.mock_mode:
            return self._mock_coaching_response(message, tips, current_score_kg, chat_history)

        # Sanitize all inputs to prevent BOM/encoding issues
        message = _sanitize_text(message)
        tips = [_sanitize_text(t) for t in tips]

        # Structure chat history for Gemini
        formatted_history = []
        for turn in chat_history[-6:]:
            role = "user" if turn["role"] == "user" else "model"
            content = _sanitize_text(turn.get('content', ''))
            formatted_history.append(f"{role.capitalize()}: {content}")
        
        history_str = "\n".join(formatted_history) if formatted_history else "(No prior conversation)"
        tips_str = "\n".join([f"- {tip}" for tip in tips]) if tips else "(No specific tips retrieved)"

        system_prompt = _sanitize_text("""
You are "Eco-Coach", an intelligent, empathetic AI sustainability assistant for the EcoSphere AI platform.

CORE PERSONALITY:
- Warm, encouraging, knowledgeable, and non-judgmental
- You give SPECIFIC, ACTIONABLE advice — never generic platitudes
- You ALWAYS answer the user's actual question directly before offering additional tips
- You are culturally sensitive and globally aware

CRITICAL RULES:
1. CULTURAL & DIETARY AWARENESS: Pay close attention to ANY cultural, religious, or dietary cues in the conversation. If a user mentions being Hindu, Muslim, Jewish, Buddhist, Jain, vegan, vegetarian, or any other identity — NEVER suggest foods that conflict with their beliefs. For example:
   - Hindu users: Do NOT suggest beef or cow-related products
   - Muslim/Jewish users: Do NOT suggest pork
   - Vegan users: Do NOT suggest any animal products
   - Jain users: Do NOT suggest root vegetables or any animal products
   Instead, suggest culturally appropriate plant-based alternatives.

2. CONTEXT-AWARENESS: Read the ENTIRE chat history carefully. Remember what the user has told you. Don't repeat yourself. Don't re-introduce yourself mid-conversation.

3. DIRECT ANSWERS: If the user asks a specific question (e.g., "Is driving an EV eco-friendly?"), give a direct, well-reasoned answer with data/facts — don't dodge with generic tips.

4. PERSONALIZATION: Use the user's carbon footprint score when relevant, but don't force it into every response.

5. FORMAT: Use markdown formatting (bold, bullet points) for readability. Keep responses concise (3-6 sentences + bullets if needed). Don't write essays.

6. NO CANNED INTROS: Don't start every message with "Hello! I am your Eco-Coach". Only introduce yourself on the very first message of a conversation.
""")

        user_prompt = _sanitize_text(f"""CONTEXT:
- User's tracked carbon footprint: {current_score_kg} kg CO2e
- Relevant sustainability tips from our knowledge base:
{tips_str}

CONVERSATION HISTORY:
{history_str}

CURRENT USER MESSAGE: {message}

Respond naturally and helpfully. Remember: answer their question FIRST, then offer 2-3 specific tips if appropriate.""")

        try:
            # Try Gemini first
            if self.client:
                response = self.client.models.generate_content(
                    model=self.MODEL_FLASH,
                    contents=[
                        types.Content(role="user", parts=[types.Part.from_text(text=system_prompt + "\n\n" + user_prompt)])
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        top_p=0.9,
                        max_output_tokens=800
                    )
                )
                return response.text
        except Exception as e:
            logger.error("Gemini coaching failed: %s", e)
        
        # Try Groq fallback
        if self.groq_client:
            groq_result = self._groq_generate(system_prompt, user_prompt, temperature=0.7, max_tokens=800)
            if groq_result:
                return groq_result
        
        # Final fallback to mock
        return self._mock_coaching_response(message, tips, current_score_kg, chat_history)

    # --- MOCK IMPLEMENTATIONS ---
    
    def _mock_parse_natural_language(self, text: str) -> List[Dict[str, Any]]:
        text_lower = text.lower()
        activities = []
        
        # Look for transit patterns
        if "drive" in text_lower or "drove" in text_lower or "car" in text_lower or "km" in text_lower:
            # Attempt to extract numbers
            kms = 15.0
            match = re.search(r'(\d+)\s*(?:km|miles|kilometer)', text_lower)
            if match:
                kms = float(match.group(1))
            
            sub = "car_petrol"
            if "electric" in text_lower or "ev" in text_lower:
                sub = "car_electric"
            elif "diesel" in text_lower:
                sub = "car_diesel"
                
            calc = calculate_footprint("transit", sub, kms)
            activities.append({
                "category": "transit",
                "subcategory": sub,
                "quantity": kms,
                "unit": "km",
                "description": f"Drove {kms} km in a {sub.replace('_', ' ')}",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
            
        if "flew" in text_lower or "flight" in text_lower or "fly" in text_lower:
            kms = 800.0
            match = re.search(r'(\d+)\s*(?:km|miles|kilometer|flight)', text_lower)
            if match:
                kms = float(match.group(1))
            
            sub = "flight_economy"
            if "business" in text_lower or "first class" in text_lower:
                sub = "flight_business"
                
            calc = calculate_footprint("transit", sub, kms)
            activities.append({
                "category": "transit",
                "subcategory": sub,
                "quantity": kms,
                "unit": "km",
                "description": f"Flew {kms} km on a {sub.replace('_', ' ')}",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })

        # Food patterns
        if "beef" in text_lower or "steak" in text_lower or "burger" in text_lower:
            calc = calculate_footprint("food", "beef_kg", 0.25)
            activities.append({
                "category": "food",
                "subcategory": "beef_kg",
                "quantity": 0.25,
                "unit": "kg",
                "description": "Had a beef meal",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
        elif "chicken" in text_lower or "poultry" in text_lower:
            calc = calculate_footprint("food", "poultry_kg", 0.25)
            activities.append({
                "category": "food",
                "subcategory": "poultry_kg",
                "quantity": 0.25,
                "unit": "kg",
                "description": "Had poultry/chicken meal",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
        elif "vegan" in text_lower:
            calc = calculate_footprint("food", "meal_vegan", 1.0)
            activities.append({
                "category": "food",
                "subcategory": "meal_vegan",
                "quantity": 1.0,
                "unit": "meals",
                "description": "Had a vegan meal",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
        elif "vegetarian" in text_lower or "veg" in text_lower:
            calc = calculate_footprint("food", "meal_vegetarian", 1.0)
            activities.append({
                "category": "food",
                "subcategory": "meal_vegetarian",
                "quantity": 1.0,
                "unit": "meals",
                "description": "Had a vegetarian meal",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
            
        # Energy patterns
        if "electricity" in text_lower or "kwh" in text_lower or "bill" in text_lower:
            kwh = 120.0
            match = re.search(r'(\d+)\s*(?:kwh|units)', text_lower)
            if match:
                kwh = float(match.group(1))
            calc = calculate_footprint("energy", "electricity_kwh", kwh)
            activities.append({
                "category": "energy",
                "subcategory": "electricity_kwh",
                "quantity": kwh,
                "unit": "kWh",
                "description": f"Used {kwh} kWh of electricity",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })

        # General fallback if no patterns matched
        if not activities:
            calc = calculate_footprint("food", "meal_standard", 1.0)
            activities.append({
                "category": "food",
                "subcategory": "meal_standard",
                "quantity": 1.0,
                "unit": "meals",
                "description": f"Logged activity: {text}",
                "carbon_kg": calc["carbon_kg"],
                "explanation": calc["calculation_basis"]
            })
            
        return activities

    def _mock_parse_receipt(self, file_mime: str) -> Dict[str, Any]:
        # Generate a realistic mock receipt depending on MIME type
        is_pdf = "pdf" in file_mime.lower()
        
        if is_pdf:
            # Mock utility bill
            calc = calculate_footprint("energy", "electricity_kwh", 150.0)
            return {
                "merchant": "State Electricity Board",
                "date": "2026-06-01",
                "total_amount": 1250.0,
                "is_utility_bill": True,
                "items": [
                    {
                        "name": "Electricity Consumption Charges",
                        "quantity": 150.0,
                        "price": 1200.0,
                        "carbon_category": "energy",
                        "carbon_subcategory": "electricity_kwh",
                        "units": "kWh",
                        "carbon_kg": calc["carbon_kg"]
                    },
                    {
                        "name": "Meter Rent",
                        "quantity": 1.0,
                        "price": 50.0,
                        "carbon_category": "other",
                        "carbon_subcategory": "",
                        "units": "unit",
                        "carbon_kg": 0.0
                    }
                ],
                "estimated_total_carbon_kg": calc["carbon_kg"]
            }
        else:
            # Mock grocery receipt
            calc_beef = calculate_footprint("food", "beef_kg", 0.50)
            calc_poultry = calculate_footprint("food", "poultry_kg", 1.20)
            
            return {
                "merchant": "GreenMart Supermarket",
                "date": "2026-06-09",
                "total_amount": 845.0,
                "is_utility_bill": False,
                "items": [
                    {
                        "name": "Fresh Beef Sirloin",
                        "quantity": 0.50,
                        "price": 450.0,
                        "carbon_category": "food",
                        "carbon_subcategory": "beef_kg",
                        "units": "kg",
                        "carbon_kg": calc_beef["carbon_kg"]
                    },
                    {
                        "name": "Organic Chicken Breast",
                        "quantity": 1.20,
                        "price": 280.0,
                        "carbon_category": "food",
                        "carbon_subcategory": "poultry_kg",
                        "units": "kg",
                        "carbon_kg": calc_poultry["carbon_kg"]
                    },
                    {
                        "name": "Local Apples",
                        "quantity": 1.50,
                        "price": 115.0,
                        "carbon_category": "other",
                        "carbon_subcategory": "",
                        "units": "kg",
                        "carbon_kg": 0.0
                    }
                ],
                "estimated_total_carbon_kg": round(calc_beef["carbon_kg"] + calc_poultry["carbon_kg"], 2)
            }

    def _mock_coaching_response(self, message: str, tips: List[str], current_score_kg: float, chat_history: List[Dict[str, str]] = None) -> str:
        """Context-aware, culturally-sensitive mock coaching response generator.
        
        Instead of returning static hardcoded strings, this:
        1. Reads full conversation history to avoid repetition and track identity
        2. Detects cultural/religious/dietary identities and filters advice accordingly
        3. Generates dynamic, varied responses using composable response fragments
        4. Directly answers the user's actual question before offering tips
        """
        import random
        import hashlib
        
        msg_lower = message.lower().strip()
        chat_history = chat_history or []
        
        # --- 1. BUILD FULL CONVERSATION CONTEXT ---
        all_user_text = " ".join(
            turn.get("content", "").lower()
            for turn in chat_history
            if turn.get("role") == "user"
        ) + " " + msg_lower
        
        all_assistant_text = " ".join(
            turn.get("content", "").lower()
            for turn in chat_history
            if turn.get("role") == "assistant"
        )
        
        # Track what topics have already been discussed
        topics_discussed = set()
        topic_keywords = {
            "transit": ["car", "drive", "commute", "flight", "fly", "bus", "train", "travel", "transit"],
            "food": ["food", "diet", "eat", "meal", "cooking", "grocery", "meat", "vegan", "vegetarian"],
            "energy": ["energy", "electricity", "power", "bill", "appliance", "ac", "heating", "cooling", "solar"],
            "waste": ["waste", "recycle", "trash", "compost", "plastic", "landfill"],
            "ev": ["ev", "electric vehicle", "electric car", "tesla", "hybrid"],
        }
        for topic, kws in topic_keywords.items():
            if any(kw in all_assistant_text for kw in kws):
                topics_discussed.add(topic)
        
        # --- 2. DETECT CULTURAL / DIETARY IDENTITY ---
        user_identity = {
            "hindu": False, "muslim": False, "jewish": False, "jain": False,
            "buddhist": False, "sikh": False, "christian": False,
            "vegan": False, "vegetarian": False, "pescatarian": False,
            "indian": False, "south_asian": False, "east_asian": False,
            "middle_eastern": False, "african": False, "latin_american": False,
        }
        identity_keywords = {
            "hindu": ["hindu", "hinduism", "mandir", "temple", "diwali", "navratri"],
            "muslim": ["muslim", "islam", "halal", "ramadan", "eid", "mosque", "masjid"],
            "jewish": ["jewish", "kosher", "synagogue", "shabbat", "hanukkah"],
            "jain": ["jain", "jainism", "ahimsa"],
            "buddhist": ["buddhist", "buddhism"],
            "sikh": ["sikh", "sikhism", "gurdwara", "langar"],
            "vegan": ["vegan", "plant-based", "plant based"],
            "vegetarian": ["vegetarian", "veggie", "no meat", "don't eat meat", "i am veg", "i'm veg"],
            "pescatarian": ["pescatarian", "only fish"],
            "indian": ["india", "indian", "delhi", "mumbai", "bangalore", "kolkata", "chennai", "hyderabad", "pune"],
            "south_asian": ["pakistan", "bangladesh", "sri lanka", "nepal"],
            "east_asian": ["china", "japan", "korea", "chinese", "japanese", "korean"],
            "middle_eastern": ["middle east", "saudi", "dubai", "uae", "qatar", "iran"],
            "african": ["nigeria", "kenya", "south africa", "ghana", "african"],
            "latin_american": ["mexico", "brazil", "argentina", "colombian", "latin"],
        }
        for identity, kws in identity_keywords.items():
            if any(kw in all_user_text for kw in kws):
                user_identity[identity] = True
        
        # Infer dietary restrictions from identity
        avoid_foods = set()
        preferred_alternatives = []
        
        if user_identity["hindu"]:
            avoid_foods.update(["beef", "cow", "steak", "veal"])
            preferred_alternatives = ["paneer", "dal (lentils)", "chickpeas", "tofu", "seasonal vegetables"]
        if user_identity["muslim"] or user_identity["jewish"]:
            avoid_foods.update(["pork", "bacon", "ham", "lard"])
            preferred_alternatives = ["legumes", "grains", "chicken", "fish", "seasonal vegetables"]
        if user_identity["jain"]:
            avoid_foods.update(["beef", "pork", "chicken", "fish", "egg", "onion", "garlic", "potato", "root vegetable"])
            preferred_alternatives = ["mung beans", "lentils", "leafy greens", "fruits", "milk-based proteins"]
        if user_identity["vegan"]:
            avoid_foods.update(["beef", "pork", "chicken", "fish", "egg", "dairy", "cheese", "milk", "butter", "yogurt"])
            preferred_alternatives = ["tofu", "tempeh", "lentils", "quinoa", "nuts and seeds"]
        if user_identity["vegetarian"]:
            avoid_foods.update(["beef", "pork", "chicken", "fish", "meat"])
            preferred_alternatives = ["paneer", "lentils", "beans", "tofu", "dairy"]
        if user_identity["sikh"]:
            # Many Sikhs are vegetarian; Sikh langar is always vegetarian
            preferred_alternatives = ["langar-style dal", "roti", "seasonal sabzi", "rice", "yogurt"]
        
        # --- 3. FILTER TIPS TO RESPECT CULTURAL IDENTITY ---
        def is_tip_safe(tip: str) -> bool:
            tip_lower = tip.lower()
            for banned_word in avoid_foods:
                if banned_word in tip_lower:
                    return False
            return True
        
        safe_tips = [t for t in tips if is_tip_safe(t)]
        if not safe_tips:
            # Provide culturally-aware fallback tips
            safe_tips = [
                "Choose seasonal, locally-sourced produce to minimize food miles.",
                "Switch off standby appliances to cut 5-10% from your electricity bill.",
                "Walk or cycle for trips under 3 km — zero emissions and great for health."
            ]
            if preferred_alternatives:
                safe_tips.insert(0, f"Try protein-rich options like {', '.join(preferred_alternatives[:3])} — low-carbon and nutritious.")
        
        tips_bullets = "\n".join([f"• {tip}" for tip in safe_tips[:4]])
        
        # --- 4. DETERMINE RESPONSE TYPE ---
        # Use message hash for deterministic but varied responses
        msg_hash = int(hashlib.md5(message.encode()).hexdigest(), 16)
        is_first_message = len(chat_history) == 0
        is_question = "?" in message or any(message.lower().startswith(w) for w in ["is ", "are ", "can ", "do ", "does ", "how ", "what ", "why ", "which ", "should "])
        
        # Varied openers — never the same stale intro
        openers_general = [
            "Great question!",
            "That's worth exploring.",
            "Interesting — let me break this down.",
            "Good thinking.",
            "Here's what the research shows.",
        ]
        openers_followup = [
            "Building on our conversation —",
            "Good follow-up.",
            "Continuing from earlier —",
            "To add to what we discussed —",
        ]
        
        # Pick opener based on context
        if is_first_message:
            opener = ""
        elif len(chat_history) > 4:
            opener = openers_followup[msg_hash % len(openers_followup)] + " "
        else:
            opener = openers_general[msg_hash % len(openers_general)] + " "
        
        # --- 5. GREETING ---
        if msg_lower in ["hello", "hi", "hey", "hi there", "hello there", "hey there", "namaste", "salaam", "salam"]:
            greeting_responses = [
                f"Hello! I'm your **Eco-Coach** 🌿. I'm here to help you understand your environmental impact and find practical ways to reduce it.\n\nYour current tracked footprint is **{current_score_kg} kg CO2e**. What would you like to explore?",
                f"Hey there! 🌿 Welcome to Eco-Coach. I can help you track carbon impact, understand your habits, and discover smarter alternatives.\n\nYou're currently at **{current_score_kg} kg CO2e**. Ask me anything — from food choices to energy savings!",
                f"Hi! 🌱 I'm Eco-Coach, your sustainability assistant. Whether it's about commuting, cooking, or energy use — I've got data-backed advice for you.\n\nYour footprint so far: **{current_score_kg} kg CO2e**. What's on your mind?",
            ]
            return greeting_responses[msg_hash % len(greeting_responses)]
        
        # --- 6. SPECIFIC TOPIC RESPONSES (context-aware) ---
        
        # EV / Electric vehicle questions
        if any(kw in msg_lower for kw in ["ev", "electric vehicle", "electric car", "hybrid", "tesla"]):
            ev_responses = [
                f"{opener}**Yes, EVs are significantly better** for the climate compared to petrol/diesel cars over their full lifecycle:\n\n• An EV produces **50-70% fewer CO2 emissions** over its lifetime than a comparable petrol car.\n• If your electricity comes from renewables, the gap widens even further.\n• Battery production has an upfront carbon cost (~6-8 tonnes CO2), typically offset within **1.5-2 years** of driving.\n• EVs eliminate tailpipe pollutants (NOx, PM2.5), improving local air quality immediately.\n\n**Practical tip:** Charge during off-peak hours when grid carbon intensity is lowest.",
                f"{opener}**EVs are a clear win for emissions**, though the picture has nuance:\n\n• Lifecycle emissions are **50-70% lower** than internal combustion engines — and improving as grids get cleaner.\n• The carbon payback period on battery manufacturing is typically under 2 years of normal driving.\n• In countries with coal-heavy grids, the benefit is smaller but still positive; in renewable-heavy grids, it's dramatic.\n• **Plug-in hybrids** offer a middle ground if charging infrastructure is limited in your area.\n\nYour current footprint is **{current_score_kg} kg CO2e** — switching to EV commuting could meaningfully reduce the transit portion."
            ]
            return ev_responses[msg_hash % len(ev_responses)]
        
        # Carbon score / footprint questions
        if any(kw in msg_lower for kw in ["score", "footprint", "how much", "my carbon", "my impact", "total"]):
            score_context = ""
            if current_score_kg < 5:
                score_context = "That's quite low — you're making good choices!"
            elif current_score_kg < 20:
                score_context = "That's moderate — there's room for targeted improvements."
            elif current_score_kg < 50:
                score_context = "That's in the higher range — but focused changes in 1-2 areas can bring it down significantly."
            else:
                score_context = "That's elevated, but don't worry — even a few habit changes can make a big impact."
            
            return f"{opener}Your current tracked footprint is **{current_score_kg} kg CO2e**. {score_context}\n\nHere are targeted recommendations:\n\n{tips_bullets}\n\nWould you like to drill into a specific category — transit, food, or energy?"
        
        # Transit / travel / driving
        if any(kw in msg_lower for kw in ["drive", "car", "commute", "travel", "transit", "flight", "fly", "bus", "train", "bike", "cycle", "walk"]):
            transit_facts = [
                "**Public transit** emits 45-80% less CO2 per km than solo driving.",
                "**Carpooling** with even one other person halves your per-trip emissions.",
                "**Economy class** produces ~50% fewer emissions per passenger than business class on flights.",
                "Eco-driving habits (smooth acceleration, proper tire pressure) cut fuel use by **15-20%**.",
                "A **10-km daily cycle commute** saves roughly 0.5 tonnes of CO2 per year vs. driving.",
                "**Remote work** even 2 days/week can cut commute emissions by 40%.",
            ]
            # Pick facts that haven't been mentioned in prior assistant messages
            fresh_facts = [f for f in transit_facts if _extract_bold_key(f) not in all_assistant_text] or transit_facts
            selected = fresh_facts[:4]
            facts_str = "\n".join([f"• {f}" for f in selected])
            
            return f"{opener}Transportation is typically the **largest contributor** to personal emissions. Here's what matters most:\n\n{facts_str}\n\nYour footprint is **{current_score_kg} kg CO2e**. Even small shifts in how you commute add up over months."
        
        # Food / diet / eating (with cultural awareness)
        if any(kw in msg_lower for kw in ["food", "diet", "eat", "meal", "cooking", "grocery", "recipe", "protein", "lunch", "dinner", "breakfast"]):
            food_tips = []
            
            # Build culturally-appropriate food advice
            if user_identity["vegan"]:
                food_tips = [
                    "You're already making one of the biggest positive choices! **Plant-based diets** produce 50-90% fewer emissions.",
                    f"Focus on **seasonal, local produce** to further minimize food miles.",
                    "**Legumes and whole grains** (lentils, quinoa, brown rice) are the most carbon-efficient protein sources.",
                    "Reducing food waste is the next frontier — meal planning can cut household waste by 25%.",
                ]
            elif user_identity["vegetarian"] or user_identity["hindu"] or user_identity["jain"]:
                food_tips = [
                    "Vegetarian diets already have a **significantly lower carbon footprint** than meat-based ones.",
                    f"Great protein sources: **{', '.join(preferred_alternatives[:3]) if preferred_alternatives else 'dal, paneer, chickpeas'}** — all low-carbon.",
                    "**Seasonal and local produce** reduces transport emissions and is often fresher and cheaper.",
                    "Try reducing dairy gradually if comfortable — plant-based milk has **~1/3 the carbon footprint** of cow's milk.",
                ]
                if user_identity["jain"]:
                    food_tips[3] = "Focus on **above-ground vegetables and fruits** — they're low-carbon and align with your values."
            elif user_identity["muslim"] or user_identity["jewish"]:
                food_tips = [
                    "**Poultry and fish** have significantly lower carbon footprints than red meat (6-7 vs 27 kg CO2e/kg).",
                    f"Protein-rich options like **{', '.join(preferred_alternatives[:3]) if preferred_alternatives else 'legumes, chicken, fish'}** are excellent low-carbon choices.",
                    "**Seasonal local produce** cuts emissions from transport and cold storage.",
                    "Reducing food waste during meal prep can cut household emissions by up to 8%.",
                ]
            else:
                food_tips = [
                    "**Plant-based meals** produce 50-90% fewer emissions than meat-heavy ones.",
                    "**Seasonal, local produce** cuts emissions from refrigerated transport and storage.",
                    "**Reducing food waste** is one of the top climate solutions — plan meals and use leftovers creatively.",
                    "Legumes (lentils, chickpeas, beans) are protein-rich with a fraction of the carbon cost of meat.",
                ]
            
            # Avoid repeating what we already said
            fresh_tips = [t for t in food_tips if _extract_bold_key(t) not in all_assistant_text] or food_tips[:3]
            tips_str = "\n".join([f"• {t}" for t in fresh_tips[:4]])
            
            return f"{opener}Food choices have a measurable impact on your footprint. Here's what's most relevant for you:\n\n{tips_str}\n\nYour footprint is **{current_score_kg} kg CO2e**. Even swapping 2-3 meals a week can make a measurable difference!"
        
        # Energy / electricity / home
        if any(kw in msg_lower for kw in ["energy", "electricity", "power", "bill", "appliance", "ac", "heating", "cooling", "solar", "led", "bulb", "fan", "geyser"]):
            energy_facts = [
                "**LED bulbs** use 85% less energy than incandescent — one of the easiest swaps.",
                "**Unplugging standby devices** saves 5-10% of household electricity.",
                "Setting AC just **1-2°C higher** in summer reduces HVAC energy by ~10%.",
                "**Cold water laundry** saves 90% of a washing machine's energy per load.",
                "**Smart power strips** auto-cut power to devices in standby mode.",
                "A **5-star rated AC** can save 20-30% energy compared to a 3-star unit.",
                "**Solar water heaters** can eliminate 50-70% of your water heating electricity.",
            ]
            fresh_facts = [f for f in energy_facts if _extract_bold_key(f) not in all_assistant_text] or energy_facts[:4]
            facts_str = "\n".join([f"• {f}" for f in fresh_facts[:4]])
            
            return f"{opener}Home energy is a great area for quick, money-saving wins:\n\n{facts_str}\n\nYour tracked footprint: **{current_score_kg} kg CO2e**. Many of these changes pay for themselves within months!"
        
        # Waste / recycling
        if any(kw in msg_lower for kw in ["waste", "recycle", "trash", "compost", "plastic", "landfill", "garbage"]):
            return f"{opener}Waste management has a bigger climate impact than most people realize:\n\n• **Food waste in landfills** generates methane, which is 80x more potent than CO2 over 20 years.\n• **Composting** organic waste reduces methane and creates nutrient-rich soil.\n• **Recycling metals** (especially aluminum) saves 90-95% of the energy needed for virgin production.\n• Carrying **reusable bags, bottles, and containers** eliminates significant single-use plastic waste.\n\nYour footprint: **{current_score_kg} kg CO2e**. Waste reduction is one of the most underrated climate actions."
        
        # Specific factual questions
        if is_question:
            # Try to give a direct, thoughtful answer
            return f"{opener}Based on sustainability research and data:\n\n{tips_bullets}\n\nYour tracked footprint is **{current_score_kg} kg CO2e**. I can dive deeper into any of these areas — just ask!"
        
        # --- 7. GENERAL / FALLBACK (still dynamic) ---
        general_closers = [
            "What specific area would you like to dive deeper into?",
            "Want me to focus on transit, food, or energy next?",
            "I can break down any category in more detail — just say the word.",
            "Shall I help you set a specific reduction target?",
        ]
        closer = general_closers[msg_hash % len(general_closers)]
        
        return f"{opener}Here are some relevant insights for you:\n\n{tips_bullets}\n\nYour current tracked footprint is **{current_score_kg} kg CO2e**. Every small change compounds over time. {closer}"

# Singleton Instance
gemini_service = GeminiService()
