import json
import re
import unicodedata
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.carbon_calc import calculate_footprint

# Try importing the new Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

def _sanitize_text(text: str) -> str:
    """Remove BOM characters and other invisible Unicode that break API calls."""
    if not text:
        return text
    # Strip BOM (\ufeff) and other zero-width chars
    text = text.replace('\ufeff', '').replace('\ufffe', '')
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    return text.strip()


class GeminiService:
    # Use the latest model that works with google-genai SDK
    MODEL_FLASH = 'gemini-2.0-flash'
    MODEL_PRO = 'gemini-2.0-flash'  # Use flash for all — fast + capable
    MODEL_EMBEDDING = 'text-embedding-004'

    def __init__(self):
        self.mock_mode = settings.USE_MOCK_SERVICES or not GENAI_AVAILABLE or (not settings.GEMINI_API_KEY and settings.ENV != "production")
        self.client = None
        if not self.mock_mode:
            try:
                # Initialize Google GenAI client
                api_key = _sanitize_text(settings.GEMINI_API_KEY)
                if api_key:
                    self.client = genai.Client(api_key=api_key)
                else:
                    self.client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location="us-central1")
                print(f"Gemini client initialized successfully. Model: {self.MODEL_FLASH}")
            except Exception as e:
                print(f"Error initializing real Gemini Client: {e}. Falling back to mock mode.")
                self.mock_mode = True

    def parse_natural_language_log(self, text: str) -> List[Dict[str, Any]]:
        """
        Parses unstructured natural language into structured carbon logs.
        Returns a list of logs with category, subcategory, quantity, description, carbon_kg, and calculation details.
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
        try:
            response = self.client.models.generate_content(
                model=self.MODEL_PRO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            raw_json = response.text.strip()
            activities = json.loads(raw_json)
            
            # Enrich activities with actual carbon calculations
            for activity in activities:
                calc = calculate_footprint(
                    activity["category"],
                    activity["subcategory"],
                    float(activity.get("quantity", 1))
                )
                activity["carbon_kg"] = calc["carbon_kg"]
                activity["explanation"] = calc["calculation_basis"]
            
            return activities
        except Exception as e:
            print(f"Error parsing log with Gemini Pro: {e}. Falling back to mock parsing.")
            return self._mock_parse_natural_language(text)

    def parse_receipt(self, file_bytes: bytes, file_mime: str) -> Dict[str, Any]:
        """
        Parses receipt or utility bill using Gemini Flash multimodal capabilities.
        """
        if self.mock_mode:
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
            print(f"Error parsing receipt with Gemini Flash: {e}. Falling back to mock receipt OCR.")
            return self._mock_parse_receipt(file_mime)

    def generate_coaching_response(self, message: str, chat_history: List[Dict[str, str]], tips: List[str], current_score_kg: float) -> str:
        """
        Generates conversational eco-coaching responses utilizing injected RAG tips.
        Uses a comprehensive system prompt to be culturally aware, context-sensitive,
        and give genuinely helpful sustainability advice.
        """
        if self.mock_mode:
            return self._mock_coaching_response(message, tips, current_score_kg)

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
            print(f"Error calling Eco-Coach Gemini API: {e}. Falling back to mock response.")
            import traceback
            traceback.print_exc()
            return self._mock_coaching_response(message, tips, current_score_kg)

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

    def _mock_coaching_response(self, message: str, tips: List[str], current_score_kg: float) -> str:
        """Improved mock response that's at least category-aware and doesn't give canned intros."""
        msg_lower = message.lower()
        
        tips_bullets = "\n".join([f"• {tip}" for tip in tips])
        if not tips:
            tips_bullets = "• Switch off appliances at the socket to eliminate standby energy loss.\n• Take public transport, cycle, or walk for journeys under 5 km.\n• Incorporate more plant-based days into your weekly diet."
        
        # EV-specific question
        if "ev" in msg_lower or "electric vehicle" in msg_lower or "electric car" in msg_lower:
            return f"Great question! **Yes, EVs are significantly more eco-friendly** than internal combustion engine vehicles over their lifetime, even accounting for battery production and electricity generation:\n\n• An average EV produces **50-70% fewer lifecycle CO2 emissions** than a petrol car.\n• The carbon footprint decreases further if your electricity grid uses renewables.\n• Battery manufacturing does have an upfront carbon cost (~6-8 tonnes CO2), but this is offset within 1.5-2 years of driving.\n• EVs also eliminate tailpipe NOx and particulate emissions, improving local air quality.\n\n**Pro tip:** If you charge during off-peak hours when grid demand is low, your carbon impact is even smaller. Your current footprint is **{current_score_kg} kg CO2e**."

        # Greeting — only respond to pure greetings, not words containing 'hi'
        if msg_lower.strip() in ["hello", "hi", "hey", "hi there", "hello there", "hey there"]:
            return f"Hello! I'm your **Eco-Coach** 🌿. I'm here to help you log activities, estimate carbon impact, and discover practical lifestyle changes.\n\nYour current tracked footprint is **{current_score_kg} kg CO2e**. What would you like to explore today?"

        if "log" in msg_lower or "carbon" in msg_lower or "score" in msg_lower or "footprint" in msg_lower:
            return f"Your current tracked footprint is **{current_score_kg} kg CO2e**. Here are personalized tips to help reduce it further:\n\n{tips_bullets}\n\nWould you like specific advice on transit, food, or energy?"

        if any(w in msg_lower for w in ["transit", "travel", "car", "drive", "commute", "flight", "fly"]):
            return f"Transportation is often the **largest contributor** to personal carbon emissions. Here's what the data shows:\n\n• **Public transit** emits 45-80% less CO2 per km than solo driving.\n• **Carpooling** with just one other person cuts your per-trip emissions in half.\n• For flights, **economy class** produces ~50% less emissions per passenger than business class.\n• Even eco-driving habits (smooth acceleration, proper tire pressure) can cut fuel use by 15-20%.\n\nYour current score is **{current_score_kg} kg CO2e**. Small shifts in how you commute can make a big difference!"
            
        if any(w in msg_lower for w in ["food", "diet", "eat", "meal", "cooking", "grocery"]):
            return f"Food choices have a huge impact on your carbon footprint! Here are evidence-based strategies:\n\n• **Plant-based meals** produce 50-90% fewer emissions than meat-heavy ones.\n• **Seasonal, local produce** cuts emissions from refrigerated transport and storage.\n• **Reducing food waste** is one of the top climate solutions — plan meals ahead and use leftovers creatively.\n• Legumes (lentils, chickpeas, beans) are protein-rich with a fraction of the carbon cost of meat.\n\nYour footprint is currently **{current_score_kg} kg CO2e**. Even swapping 2-3 meals a week to plant-based can make a measurable dent!"

        if any(w in msg_lower for w in ["energy", "electricity", "power", "bill", "appliance", "ac", "heating", "cooling"]):
            return f"Home energy use is a great area for quick wins! Here's what works:\n\n• **LED bulbs** use 85% less energy than incandescent — swap them first.\n• **Unplug electronics** when not in use; standby power is 5-10% of your bill.\n• Set your AC 1-2°C higher in summer (or lower in winter) to reduce HVAC energy by ~10%.\n• **Cold water laundry** saves 90% of the energy a washing machine uses.\n\nYour tracked footprint: **{current_score_kg} kg CO2e**. These changes often save money too!"

        # General/unknown topic — give a thoughtful response
        return f"That's a thoughtful question! Here are some relevant insights based on sustainability research:\n\n{tips_bullets}\n\nYour current tracked footprint is **{current_score_kg} kg CO2e**. Every small change compounds over time — what specific area would you like to dive deeper into?"

# Singleton Instance
gemini_service = GeminiService()
