import time
from typing import List, Dict, Any, Optional
from backend.config import settings

# Try importing Firestore SDK
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.vector import VectorValue
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Stateful In-Memory Mock database for offline testing
MOCK_DB = {
    "logs": [],
    "chat_history": {},
    "tips": [
        # Transit Tips
        {"category": "transit", "tip_text": "Walk or cycle for short distance trips to completely eliminate transport emissions."},
        {"category": "transit", "tip_text": "Use electric trains or buses for medium commute distances to reduce emissions by 60% compared to solo driving."},
        {"category": "transit", "tip_text": "Drive smoothly and stay under speed limits. Aggressive driving reduces fuel efficiency by 15-30%."},
        {"category": "transit", "tip_text": "Choose economy class flights and group flights together to lower transit footprint."},
        {"category": "transit", "tip_text": "Keep your car tires inflated correctly. Under-inflated tires increase fuel consumption by up to 3%."},
        # Energy Tips
        {"category": "energy", "tip_text": "Switch to LED lighting; LEDs use up to 85% less energy than standard bulbs."},
        {"category": "energy", "tip_text": "Unplug electronics when not in use; standby power accounts for 5-10% of household electricity."},
        {"category": "energy", "tip_text": "Wash clothes in cold water; heating water accounts for 90% of a washing machine's energy consumption."},
        {"category": "energy", "tip_text": "Upgrade to ENERGY STAR certified appliances to lower monthly base utility usage."},
        {"category": "energy", "tip_text": "Set your thermostat 1-2 degrees higher in summer and lower in winter to optimize HVAC footprint."},
        # Food Tips
        {"category": "food", "tip_text": "Substitute one beef meal a week with chicken or fish to cut your meal footprint by over 60%."},
        {"category": "food", "tip_text": "Eat plant-based (vegan/vegetarian) meals 2-3 times a week to significantly lower food-related greenhouse gases."},
        {"category": "food", "tip_text": "Reduce food waste by planning meals ahead. Landfill food waste generates high methane emissions."},
        {"category": "food", "tip_text": "Support local farming. Buying locally grown, seasonal food reduces food miles and transit emissions."},
        # Waste Tips
        {"category": "waste", "tip_text": "Separate paper, plastic, and metals carefully to ensure high recycling efficiency and low landfill waste."},
        {"category": "waste", "tip_text": "Compost food scraps to keep organic matter out of municipal landfills and enrich soil naturally."},
        {"category": "waste", "tip_text": "Avoid single-use plastics and carry reusable grocery bags and water bottles."}
    ]
}

class FirestoreDatabase:
    def __init__(self):
        self.mock_mode = settings.USE_MOCK_SERVICES or not FIRESTORE_AVAILABLE
        self.db = None
        if not self.mock_mode:
            try:
                self.db = firestore.Client(
                    project=settings.PROJECT_ID,
                    database=settings.FIRESTORE_DATABASE
                )
            except Exception as e:
                print(f"Error initializing real Firestore client: {e}. Falling back to Mock DB.")
                self.mock_mode = True

    # --- LOG MANAGEMENT ---
    
    def save_log(self, user_id: str, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves a carbon log entry for a specific user.
        """
        timestamp = time.time()
        log_entry = {
            "user_id": user_id,
            "category": log_data["category"],
            "subcategory": log_data["subcategory"],
            "quantity": float(log_data["quantity"]),
            "unit": log_data["unit"],
            "description": log_data["description"],
            "carbon_kg": float(log_data["carbon_kg"]),
            "explanation": log_data.get("explanation", ""),
            "timestamp": timestamp
        }
        
        if self.mock_mode:
            MOCK_DB["logs"].append(log_entry)
            return log_entry
        
        try:
            doc_ref = self.db.collection("users").document(user_id).collection("carbon_logs").document()
            doc_ref.set(log_entry)
            # Add document ID
            log_entry["id"] = doc_ref.id
            return log_entry
        except Exception as e:
            print(f"Firestore save_log failed: {e}. Saving to mock memory.")
            MOCK_DB["logs"].append(log_entry)
            return log_entry

    def get_logs(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all carbon logs for a user, sorted by timestamp descending.
        """
        if self.mock_mode:
            user_logs = [log for log in MOCK_DB["logs"] if log["user_id"] == user_id]
            return sorted(user_logs, key=lambda x: x["timestamp"], reverse=True)
            
        try:
            logs_ref = self.db.collection("users").document(user_id).collection("carbon_logs")
            query = logs_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            results = []
            for doc in query:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            return results
        except Exception as e:
            print(f"Firestore get_logs failed: {e}. Returning mock logs.")
            user_logs = [log for log in MOCK_DB["logs"] if log["user_id"] == user_id]
            return sorted(user_logs, key=lambda x: x["timestamp"], reverse=True)

    # --- CHAT STATE MANAGEMENT ---
    
    def save_chat_turn(self, session_id: str, role: str, content: str):
        """
        Saves a chat message turn to the conversation history.
        """
        turn = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        
        if self.mock_mode:
            if session_id not in MOCK_DB["chat_history"]:
                MOCK_DB["chat_history"][session_id] = []
            MOCK_DB["chat_history"][session_id].append(turn)
            return
            
        try:
            chat_ref = self.db.collection("sessions").document(session_id).collection("messages").document()
            chat_ref.set(turn)
        except Exception as e:
            print(f"Firestore save_chat_turn failed: {e}. Saving to mock memory.")
            if session_id not in MOCK_DB["chat_history"]:
                MOCK_DB["chat_history"][session_id] = []
            MOCK_DB["chat_history"][session_id].append(turn)

    def get_chat_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Retrieves the recent chat history for a session.
        """
        if self.mock_mode:
            turns = MOCK_DB["chat_history"].get(session_id, [])
            sorted_turns = sorted(turns, key=lambda x: x["timestamp"])
            return [{"role": t["role"], "content": t["content"]} for t in sorted_turns[-limit:]]
            
        try:
            messages_ref = self.db.collection("sessions").document(session_id).collection("messages")
            query = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
            results = []
            for doc in query:
                results.append(doc.to_dict())
            # Reverse to maintain chronological order
            results.reverse()
            return [{"role": r["role"], "content": r["content"]} for r in results]
        except Exception as e:
            print(f"Firestore get_chat_history failed: {e}. Returning mock chat history.")
            turns = MOCK_DB["chat_history"].get(session_id, [])
            sorted_turns = sorted(turns, key=lambda x: x["timestamp"])
            return [{"role": t["role"], "content": t["content"]} for t in sorted_turns[-limit:]]

    # --- ENVIRONMENTAL TIPS & RAG VECTOR SEARCH ---
    
    def search_tips_rag(self, query_text: str, category_hint: Optional[str] = None, limit: int = 3) -> List[str]:
        """
        Retrieves relevant environmental tips using Firestore Vector Search or Keyword Mock fallback.
        """
        if self.mock_mode:
            return self._mock_search_tips(query_text, category_hint, limit)
            
        try:
            # We generate query embedding using Gemini's text-embedding model if available,
            # then query Firestore Vector Search
            from backend.services.gemini_ops import gemini_service
            
            # If real Gemini is offline or mock, fall back to mock tip search
            if gemini_service.mock_mode or gemini_service.client is None:
                return self._mock_search_tips(query_text, category_hint, limit)
                
            # Generate embedding
            response = gemini_service.client.models.embed_content(
                model='text-embedding-004',
                contents=query_text
            )
            query_vector = response.embeddings[0].values
            
            # Run vector search query in Firestore
            tips_ref = self.db.collection("environmental_tips")
            # Query Firestore find_nearest vector search
            # (Note: environmental_tips needs to be pre-seeded in the Firestore database with embeddings)
            vector_query = tips_ref.find_nearest(
                vector_field="embedding",
                query_vector=VectorValue(query_vector),
                distance_measure=DistanceMeasure.COSINE,
                limit=limit
            )
            
            results = []
            for doc in vector_query.stream():
                results.append(doc.to_dict().get("tip_text", ""))
                
            # If no tips are stored, fall back to local seed data
            if not results:
                return self._mock_search_tips(query_text, category_hint, limit)
                
            return results
        except Exception as e:
            print(f"Firestore vector search_tips_rag failed: {e}. Falling back to mock tip matching.")
            return self._mock_search_tips(query_text, category_hint, limit)

    def _mock_search_tips(self, query_text: str, category_hint: Optional[str] = None, limit: int = 3) -> List[str]:
        """
        Simple, robust keyword and category matching for mock RAG search.
        """
        query_lower = query_text.lower()
        
        # Determine target category
        target_category = category_hint
        if not target_category:
            if any(k in query_lower for k in ["drive", "car", "travel", "flight", "flew", "transit", "train", "bus"]):
                target_category = "transit"
            elif any(k in query_lower for k in ["electric", "electricity", "bulb", "appliances", "power", "ac", "hvac", "energy"]):
                target_category = "energy"
            elif any(k in query_lower for k in ["eat", "food", "beef", "chicken", "diet", "vegan", "vegetarian", "meal"]):
                target_category = "food"
            elif any(k in query_lower for k in ["waste", "trash", "recycle", "garbage", "compost", "plastic"]):
                target_category = "waste"
                
        # Filter matching tips
        matched_tips = []
        if target_category:
            matched_tips = [tip["tip_text"] for tip in MOCK_DB["tips"] if tip["category"] == target_category]
            
        # If no category match, take a diverse mix of tips
        if not matched_tips:
            matched_tips = [tip["tip_text"] for tip in MOCK_DB["tips"]]
            
        # Shuffle/take top limits
        import random
        # Use seed for consistency or just return slice
        return matched_tips[:limit]

# Singleton Instance
firestore_db = FirestoreDatabase()
