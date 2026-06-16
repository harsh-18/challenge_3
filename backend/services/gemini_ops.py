import json
import re
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

class GeminiService:
    def __init__(self):
        self.mock_mode = settings.USE_MOCK_SERVICES or not GENAI_AVAILABLE or (not settings.GEMINI_API_KEY and settings.ENV != "production")
        self.client = None
        if not self.mock_mode:
            try:
                # Initialize Google GenAI client
                # If API Key is provided, use it, otherwise rely on Application Default Credentials (ADC)
                if settings.GEMINI_API_KEY:
                    self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                else:
                    self.client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location="us-central1")
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
                model='gemini-1.5-pro',
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
                model='gemini-1.5-flash',
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
        """
        if self.mock_mode:
            return self._mock_coaching_response(message, tips, current_score_kg)

        # Structure chat history for Gemini
        formatted_history = []
        for turn in chat_history[-6:]: # Keep last 6 turns for context
            role = "user" if turn["role"] == "user" else "model"
            formatted_history.append(f"{role.capitalize()}: {turn['content']}")
        
        history_str = "\n".join(formatted_history)
        tips_str = "\n".join([f"- {tip}" for tip in tips])

        prompt = f"""
        You are "Eco-Coach", a friendly, encouraging AI sustainability assistant.
        Your goal is to guide the user in lowering their carbon footprint using simple, practical tips.

        Context:
        - User's Current Daily/Weekly Carbon Footprint: {current_score_kg} kg CO2e.
        - Relevant Environmental Tips retrieved for this query:
        {tips_str}

        Recent Chat History:
        {history_str}

        User message: "{message}"

        Response Guidelines:
        1. Be supportive, friendly, and actionable. Don't sound lecturing or judgmental.
        2. Reference the user's carbon score if it makes sense in context.
        3. Seamlessly weave in the provided environmental tips to give highly personalized, grounded advice.
        4. Keep your answer conversational, concise, and structured with bullet points where appropriate.
        """
        try:
            response = self.client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Error calling Eco-Coach Gemini API: {e}. Falling back to mock response.")
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
        msg_lower = message.lower()
        
        tips_bullets = "\n".join([f"• {tip}" for tip in tips])
        if not tips:
            tips_bullets = "• Switch off appliances at the socket to eliminate standby energy loss.\n• Take public transport, cycle, or walk for journeys under 5 km.\n• Incorporate more plant-based days into your weekly diet."
            
        if "hello" in msg_lower or "hi" in msg_lower:
            return f"Hello! I am your **Eco-Coach** 🌿. I'm here to help you log and reduce your daily carbon footprint. Your current footprint is **{current_score_kg} kg CO2e**. What would you like to log or ask about today?"

        if "log" in msg_lower or "carbon" in msg_lower or "score" in msg_lower:
            return f"Your current tracked footprint is **{current_score_kg} kg CO2e**. Based on your activities, here are some customized tips you can follow to lower this:\n\n{tips_bullets}\n\nDo you want me to suggest specific alternatives for transit, food, or energy?"

        if "transit" in msg_lower or "travel" in msg_lower or "car" in msg_lower or "drive" in msg_lower:
            return f"Transit is typically one of the highest contributors to personal carbon emissions! With your current score of **{current_score_kg} kg CO2e**, here is what you can do:\n\n• For shorter distances, consider walking, cycling, or using public metro systems.\n• If driving, carpooling or driving in eco-mode can cut emissions by up to 20%.\n• If possible, plan flights efficiently and opt for economy class over business to halve the per-passenger emission factor."
            
        if "eat" in msg_lower or "food" in msg_lower or "diet" in msg_lower:
            return f"Food is a great area for quick wins! \n\n• Replacing just one beef meal per week with a chicken, vegetarian, or vegan option cuts that meal's emissions by 75-90%.\n• Reducing food waste helps minimize landfill methane emissions.\n• Try buying local and seasonal produce to limit emissions from transit and refrigerated storage."

        # General response
        return f"That's a great question! Reducing our footprint is about small, consistent choices. Here are some relevant recommendations based on your sustainability goals:\n\n{tips_bullets}\n\nHow else can I help you today?"

# Singleton Instance
gemini_service = GeminiService()
