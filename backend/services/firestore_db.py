"""
Firestore database service layer.

Provides log storage, chat history management, and RAG-based environmental
tip retrieval using Firestore Native Vector Search (production) or
in-memory keyword matching (mock/development).
"""
import logging
import re
import time
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple

from backend.config import settings

logger = logging.getLogger(__name__)

# Try importing Firestore SDK
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.vector import VectorValue
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Stateful In-Memory Mock database for offline testing
MOCK_DB: Dict[str, Any] = {
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
        {"category": "waste", "tip_text": "Avoid single-use plastics and carry reusable grocery bags and water bottles."},
    ],
}

# Pre-computed keyword index for efficient mock tip search
_STOPWORDS = frozenset({
    "i", "a", "an", "the", "is", "are", "am", "was", "were", "be", "been",
    "to", "of", "in", "on", "at", "for", "and", "or", "but", "not", "my",
    "me", "we", "you", "it", "do", "does", "did", "can", "how", "what",
    "this", "that", "with", "from", "have", "has", "had", "will", "would",
    "should", "could", "about", "more", "some", "very", "much", "so", "too",
})

_CATEGORY_SIGNALS: Dict[str, List[str]] = {
    "transit": ["drive", "car", "travel", "flight", "flew", "transit", "train", "bus",
                "commute", "bike", "cycle", "walk", "metro", "uber", "ride"],
    "energy": ["electric", "electricity", "bulb", "appliances", "power", "hvac", "energy",
               "solar", "led", "fan", "geyser", "heater", "cooling", "heating", "bill", "kwh"],
    "food": ["eat", "food", "beef", "chicken", "diet", "vegan", "vegetarian", "meal",
             "cooking", "grocery", "protein", "dairy", "meat", "fish", "recipe", "lunch", "dinner"],
    "waste": ["waste", "trash", "recycle", "garbage", "compost", "plastic", "landfill",
              "reuse", "reduce", "packaging", "bottle", "bag"],
}


class FirestoreDatabase:
    """Database service with automatic fallback from Firestore to in-memory mock."""

    def __init__(self) -> None:
        self.mock_mode: bool = settings.USE_MOCK_SERVICES or not FIRESTORE_AVAILABLE
        self.db = None
        if not self.mock_mode:
            try:
                self.db = firestore.Client(
                    project=settings.PROJECT_ID,
                    database=settings.FIRESTORE_DATABASE,
                )
                logger.info("Firestore client initialized for project '%s'", settings.PROJECT_ID)
            except Exception as e:
                logger.warning("Error initializing Firestore client: %s. Falling back to Mock DB.", e)
                self.mock_mode = True

    # --- LOG MANAGEMENT ---

    def save_log(self, user_id: str, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a carbon log entry for a specific user."""
        timestamp = time.time()
        log_entry: Dict[str, Any] = {
            "user_id": user_id,
            "category": log_data["category"],
            "subcategory": log_data["subcategory"],
            "quantity": float(log_data["quantity"]),
            "unit": log_data["unit"],
            "description": log_data["description"],
            "carbon_kg": float(log_data["carbon_kg"]),
            "explanation": log_data.get("explanation", ""),
            "timestamp": timestamp,
        }

        if self.mock_mode:
            MOCK_DB["logs"].append(log_entry)
            return log_entry

        try:
            doc_ref = self.db.collection("users").document(user_id).collection("carbon_logs").document()
            doc_ref.set(log_entry)
            log_entry["id"] = doc_ref.id
            return log_entry
        except Exception as e:
            logger.warning("Firestore save_log failed: %s. Saving to mock memory.", e)
            MOCK_DB["logs"].append(log_entry)
            return log_entry

    def get_logs(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch carbon logs for a user with pagination support.

        Args:
            user_id: The user's identifier.
            limit: Maximum number of logs to return.
            offset: Number of logs to skip (for pagination).
        """
        if self.mock_mode:
            user_logs = [log for log in MOCK_DB["logs"] if log["user_id"] == user_id]
            sorted_logs = sorted(user_logs, key=lambda x: x["timestamp"], reverse=True)
            return sorted_logs[offset:offset + limit]

        try:
            logs_ref = self.db.collection("users").document(user_id).collection("carbon_logs")
            query = logs_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).offset(offset).limit(limit).stream()
            results: List[Dict[str, Any]] = []
            for doc in query:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            return results
        except Exception as e:
            logger.warning("Firestore get_logs failed: %s. Returning mock logs.", e)
            user_logs = [log for log in MOCK_DB["logs"] if log["user_id"] == user_id]
            sorted_logs = sorted(user_logs, key=lambda x: x["timestamp"], reverse=True)
            return sorted_logs[offset:offset + limit]

    # --- CHAT STATE MANAGEMENT ---

    def save_chat_turn(self, session_id: str, role: str, content: str) -> None:
        """Save a chat message turn to the conversation history."""
        turn: Dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
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
            logger.warning("Firestore save_chat_turn failed: %s. Saving to mock memory.", e)
            if session_id not in MOCK_DB["chat_history"]:
                MOCK_DB["chat_history"][session_id] = []
            MOCK_DB["chat_history"][session_id].append(turn)

    def get_chat_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve the recent chat history for a session."""
        if self.mock_mode:
            turns = MOCK_DB["chat_history"].get(session_id, [])
            sorted_turns = sorted(turns, key=lambda x: x["timestamp"])
            return [{"role": t["role"], "content": t["content"]} for t in sorted_turns[-limit:]]

        try:
            messages_ref = self.db.collection("sessions").document(session_id).collection("messages")
            query = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
            results: List[Dict[str, Any]] = []
            for doc in query:
                results.append(doc.to_dict())
            # Reverse to maintain chronological order
            results.reverse()
            return [{"role": r["role"], "content": r["content"]} for r in results]
        except Exception as e:
            logger.warning("Firestore get_chat_history failed: %s. Returning mock chat history.", e)
            turns = MOCK_DB["chat_history"].get(session_id, [])
            sorted_turns = sorted(turns, key=lambda x: x["timestamp"])
            return [{"role": t["role"], "content": t["content"]} for t in sorted_turns[-limit:]]

    # --- ENVIRONMENTAL TIPS & RAG VECTOR SEARCH ---

    def search_tips_rag(self, query_text: str, category_hint: Optional[str] = None, limit: int = 3) -> List[str]:
        """
        Retrieve relevant environmental tips using Firestore Vector Search or keyword mock fallback.

        Args:
            query_text: User's query or message for semantic search.
            category_hint: Optional category filter (transit, energy, food, waste).
            limit: Maximum number of tips to return.
        """
        if self.mock_mode:
            return self._mock_search_tips(query_text, category_hint, limit)

        try:
            # Generate query embedding using Gemini's text-embedding model
            from backend.services.gemini_ops import gemini_service

            if gemini_service.mock_mode or gemini_service.client is None:
                return self._mock_search_tips(query_text, category_hint, limit)

            response = gemini_service.client.models.embed_content(
                model="text-embedding-004",
                contents=query_text,
            )
            query_vector = response.embeddings[0].values

            # Run vector search query in Firestore
            tips_ref = self.db.collection("environmental_tips")
            vector_query = tips_ref.find_nearest(
                vector_field="embedding",
                query_vector=VectorValue(query_vector),
                distance_measure=DistanceMeasure.COSINE,
                limit=limit,
            )

            results: List[str] = []
            for doc in vector_query.stream():
                results.append(doc.to_dict().get("tip_text", ""))

            if not results:
                return self._mock_search_tips(query_text, category_hint, limit)

            return results
        except Exception as e:
            logger.warning("Firestore vector search_tips_rag failed: %s. Falling back to mock.", e)
            return self._mock_search_tips(query_text, category_hint, limit)

    def _mock_search_tips(self, query_text: str, category_hint: Optional[str] = None, limit: int = 3) -> List[str]:
        """
        Relevance-scored keyword matching for mock RAG search.

        Ranks tips by query keyword overlap with category-match boosting.
        """
        query_lower = query_text.lower()
        query_words = [w for w in re.findall(r"[a-z]+", query_lower)
                       if len(w) > 2 and w not in _STOPWORDS]

        # Determine target category
        target_category = category_hint
        if not target_category:
            target_category = self._detect_category(query_lower)

        # Score each tip by relevance
        scored_tips: List[Tuple[int, str]] = []
        for tip_data in MOCK_DB["tips"]:
            tip_text = tip_data["tip_text"]
            tip_lower = tip_text.lower()
            tip_category = tip_data["category"]

            # Base score: count of query words found in tip text
            word_score = sum(1 for w in query_words if w in tip_lower)

            # Category bonus
            category_bonus = 3 if (target_category and tip_category == target_category) else 0

            # Exact phrase fragment bonus
            phrase_bonus = 0
            for i in range(len(query_words) - 1):
                bigram = f"{query_words[i]} {query_words[i + 1]}"
                if bigram in tip_lower:
                    phrase_bonus += 2

            total_score = word_score + category_bonus + phrase_bonus
            scored_tips.append((total_score, tip_text))

        # Sort by score descending, then take top N
        scored_tips.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate and return
        seen: set = set()
        results: List[str] = []
        for _score, tip in scored_tips:
            if tip not in seen:
                seen.add(tip)
                results.append(tip)
                if len(results) >= limit:
                    break

        return results

    @staticmethod
    @lru_cache(maxsize=128)
    def _detect_category(query_lower: str) -> Optional[str]:
        """Detect the most likely category from query text using keyword signals."""
        best_cat: Optional[str] = None
        best_count = 0
        for cat, signals in _CATEGORY_SIGNALS.items():
            count = sum(1 for s in signals if s in query_lower)
            if count > best_count:
                best_count = count
                best_cat = cat
        return best_cat


# Singleton Instance
firestore_db = FirestoreDatabase()
