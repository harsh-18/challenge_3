import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.gemini_ops import gemini_service
from backend.services.firestore_db import firestore_db

# Initialize FastAPI
app = FastAPI(
    title="EcoSphere AI - Carbon Footprint Platform API",
    description="Backend service powering natural language carbon logging, receipt OCR parsing, and Eco-Coach chat.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory performance metrics
START_TIME = time.time()
API_METRICS = {
    "total_logs_processed": 0,
    "receipts_parsed": 0,
    "chat_messages_exchanged": 0,
    "total_carbon_logged_kg": 0.0
}

# --- AUTH DEPENDENCY ---

def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extracts the user ID from the Authorization header.
    In mock mode, the bearer token itself is treated directly as the user ID.
    If header is missing, defaults to 'mock-user-123' to ensure zero friction.
    """
    if not authorization:
        return "mock-user-123"
        
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return "mock-user-123"
            
        token = parts[1]
        
        # Real Firebase token validation can be integrated here:
        # if not settings.USE_MOCK_SERVICES:
        #     decoded_token = auth.verify_id_token(token)
        #     return decoded_token['uid']
            
        return token
    except Exception as e:
        print(f"Auth token parsing failed: {e}")
        return "mock-user-123"

# --- PYDANTIC MODEL SCHEMAS ---

class TextLogRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=1000, description="Unstructured description of activity.")

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message to the Eco-Coach.")
    session_id: str = Field(..., description="Chat session identifier.")

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {
        "message": "Welcome to EcoSphere AI API",
        "status": "operational",
        "documentation": "/docs"
    }

@app.get("/api")
@app.get("/api/")
def api_root():
    return {
        "message": "EcoSphere AI API Gateway",
        "status": "operational"
    }

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """
    Standard health check endpoint.
    """
    # Determine active LLM provider
    if gemini_service.client:
        llm_provider = "gemini"
    elif gemini_service.groq_client:
        llm_provider = "groq"
    else:
        llm_provider = "mock"
    
    return {
        "status": "healthy",
        "mock_mode": settings.USE_MOCK_SERVICES,
        "llm_provider": llm_provider,
        "environment": settings.ENV,
        "gcp_project": settings.PROJECT_ID,
        "uptime_sec": round(time.time() - START_TIME, 2)
    }

@app.get("/api/metrics", status_code=status.HTTP_200_OK)
def get_metrics():
    """
    Returns platform metrics.
    """
    return {
        "total_logs_processed": API_METRICS["total_logs_processed"],
        "receipts_parsed": API_METRICS["receipts_parsed"],
        "chat_messages_exchanged": API_METRICS["chat_messages_exchanged"],
        "total_carbon_logged_kg": round(API_METRICS["total_carbon_logged_kg"], 2),
        "api_status": "operational"
    }

@app.post("/api/logs/text", status_code=status.HTTP_201_CREATED)
def log_natural_language_activity(
    request: TextLogRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Processes a natural language carbon log, extracts activities, calculates footprints, and saves logs.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty activity description.")
        
    try:
        # Call Gemini to parse into structured activities
        parsed_activities = gemini_service.parse_natural_language_log(request.text)
        
        saved_logs = []
        for activity in parsed_activities:
            # Save to database
            saved_log = firestore_db.save_log(user_id, activity)
            saved_logs.append(saved_log)
            
            # Update metrics
            API_METRICS["total_logs_processed"] += 1
            API_METRICS["total_carbon_logged_kg"] += saved_log["carbon_kg"]
            
        return {
            "status": "success",
            "input_text": request.text,
            "logs": saved_logs
        }
    except Exception as e:
        print(f"Failed to log text activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing carbon log: {str(e)}"
        )

@app.post("/api/logs/receipt", status_code=status.HTTP_201_CREATED)
async def log_receipt_activity(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Uploads a utility bill or grocery receipt, extracts carbon metadata via Gemini Flash OCR, and saves carbon logs.
    """
    try:
        file_bytes = await file.read()
        file_mime = file.content_type or "image/jpeg"
        
        # Parse receipt using Gemini Flash multimodal API
        parsed_receipt = gemini_service.parse_receipt(file_bytes, file_mime)
        
        merchant = parsed_receipt.get("merchant", "Receipt Upload")
        date = parsed_receipt.get("date") or time.strftime("%Y-%m-%d")
        
        saved_logs = []
        # Create carbon log entries for all items with carbon calculations
        for item in parsed_receipt.get("items", []):
            carbon_kg = float(item.get("carbon_kg", 0.0))
            if carbon_kg > 0:
                log_data = {
                    "category": item.get("carbon_category", "food"),
                    "subcategory": item.get("carbon_subcategory", ""),
                    "quantity": float(item.get("quantity", 1)),
                    "unit": item.get("units", "unit"),
                    "description": f"Receipt item: {item.get('name')} from {merchant}",
                    "carbon_kg": carbon_kg,
                    "explanation": f"Extracted from {merchant} receipt/bill."
                }
                saved_log = firestore_db.save_log(user_id, log_data)
                saved_logs.append(saved_log)
                
                # Update metrics
                API_METRICS["total_logs_processed"] += 1
                API_METRICS["total_carbon_logged_kg"] += carbon_kg
                
        API_METRICS["receipts_parsed"] += 1
        
        return {
            "status": "success",
            "merchant": merchant,
            "date": date,
            "total_amount": parsed_receipt.get("total_amount", 0.0),
            "is_utility_bill": parsed_receipt.get("is_utility_bill", False),
            "items": parsed_receipt.get("items", []),
            "estimated_total_carbon_kg": parsed_receipt.get("estimated_total_carbon_kg", 0.0),
            "saved_logs": saved_logs
        }
    except Exception as e:
        print(f"Failed to process receipt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing receipt/bill file: {str(e)}"
        )

@app.get("/api/logs", status_code=status.HTTP_200_OK)
def get_user_logs(user_id: str = Depends(get_current_user)):
    """
    Retrieves all carbon logs logged by the current user.
    """
    try:
        logs = firestore_db.get_logs(user_id)
        
        # Calculate categories summaries
        summary = {"transit": 0.0, "energy": 0.0, "food": 0.0, "waste": 0.0}
        total = 0.0
        for log in logs:
            cat = log["category"]
            carbon = log["carbon_kg"]
            if cat in summary:
                summary[cat] += carbon
            total += carbon
            
        return {
            "logs": logs,
            "summary": {
                "categories": {k: round(v, 2) for k, v in summary.items()},
                "total_carbon_kg": round(total, 2)
            }
        }
    except Exception as e:
        print(f"Failed to fetch logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve carbon log history."
        )

@app.post("/api/chat", status_code=status.HTTP_200_OK)
def chat_with_eco_coach(
    request: ChatMessageRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Conversational Eco-Coach chatbot.
    Retrieves recent chat turns, queries vector search for matching environmental tips (RAG),
    calls Gemini Flash to generate feedback, saves chat log, and returns the response.
    """
    try:
        # 1. Fetch recent logs to calculate user score context
        logs = firestore_db.get_logs(user_id)
        current_score_kg = sum(log["carbon_kg"] for log in logs[-15:]) # last 15 entries
        
        # 2. Get recent chat history
        history = firestore_db.get_chat_history(request.session_id, limit=6)
        
        # 3. Firestore Vector Search for matching environmental tips (RAG)
        injected_tips = firestore_db.search_tips_rag(request.message, limit=3)
        
        # 4. Generate chatbot response
        coach_reply = gemini_service.generate_coaching_response(
            message=request.message,
            chat_history=history,
            tips=injected_tips,
            current_score_kg=round(current_score_kg, 2)
        )
        
        # 5. Save turns to database
        firestore_db.save_chat_turn(request.session_id, "user", request.message)
        firestore_db.save_chat_turn(request.session_id, "assistant", coach_reply)
        
        API_METRICS["chat_messages_exchanged"] += 2
        
        return {
            "reply": coach_reply,
            "session_id": request.session_id,
            "tips_referenced": injected_tips
        }
    except Exception as e:
        print(f"Failed to execute chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Eco-Coach is temporarily experiencing technical difficulties."
        )

@app.get("/api/tips", status_code=status.HTTP_200_OK)
def get_green_tips(
    query: Optional[str] = None,
    category: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """
    Retrieves customized, semantic environmental recommendations using Firestore Vector search.
    """
    try:
        query_text = query or "general green lifestyle tips"
        tips = firestore_db.search_tips_rag(query_text, category_hint=category, limit=5)
        return {"tips": tips}
    except Exception as e:
        print(f"Failed to retrieve tips: {e}")
        return {"tips": [
            "Switch to public transport or bicycling for daily commutes.",
            "Incorporate more vegetable protein and reduce beef intake.",
            "Unplug power strips and electronic chargers when away."
        ]}
