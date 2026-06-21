"""
EcoSphere AI — Carbon Footprint Platform API

Backend service powering natural language carbon logging, receipt OCR parsing,
and Eco-Coach chat with RAG-based environmental recommendations.
"""
import html
import logging
import re
import time
from collections import defaultdict
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Header, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings, setup_logging
from backend.services.gemini_ops import gemini_service
from backend.services.firestore_db import firestore_db

# Configure structured logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="EcoSphere AI - Carbon Footprint Platform API",
    description="Backend service powering natural language carbon logging, receipt OCR parsing, and Eco-Coach chat.",
    version="1.0.0",
)

# GZip compression middleware for response efficiency
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS configuration — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# In-memory performance metrics
START_TIME = time.time()
API_METRICS: Dict[str, Any] = {
    "total_logs_processed": 0,
    "receipts_parsed": 0,
    "chat_messages_exchanged": 0,
    "total_carbon_logged_kg": 0.0,
}

# --- INPUT SANITIZATION HELPERS ---

_STRIP_HTML_RE = re.compile(r"<[^>]+>")


def sanitize_user_input(text: str) -> str:
    """Strip HTML tags and escape special characters to prevent injection."""
    text = _STRIP_HTML_RE.sub("", text)
    text = html.escape(text, quote=True)
    return text.strip()


# --- GLOBAL EXCEPTION HANDLER ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler to prevent leaking stack traces to clients."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# --- SECURITY & RATE LIMITING MIDDLEWARE ---

RATE_LIMIT_WINDOW = 60  # seconds (1 minute)
RATE_LIMIT_MAX_REQUESTS = 100  # maximum requests per minute per IP
ip_request_history = defaultdict(list)


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # 1. Rate Limiting for API routes
    if request.url.path.startswith("/api"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean up history and check limit
        ip_request_history[client_ip] = [t for t in ip_request_history[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(ip_request_history[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again in a minute."},
            )
        ip_request_history[client_ip].append(now)

    # 2. Process Request
    response = await call_next(request)

    # 3. Add Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


# --- AUTH DEPENDENCY ---

def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract the user ID from the Authorization header.

    In mock mode, the bearer token itself is treated directly as the user ID.
    If the header is missing, defaults to 'mock-user-123' for zero-friction testing.
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
        logger.warning("Auth token parsing failed: %s", e)
        return "mock-user-123"


# --- PYDANTIC REQUEST/RESPONSE SCHEMAS ---

class TextLogRequest(BaseModel):
    """Request body for natural language carbon log submission."""
    text: str = Field(..., min_length=2, max_length=1000, description="Unstructured description of activity.")


class ChatMessageRequest(BaseModel):
    """Request body for Eco-Coach chat messages."""
    message: str = Field(..., min_length=1, max_length=2000, description="Message to the Eco-Coach.")
    session_id: str = Field(..., min_length=1, max_length=100, description="Chat session identifier.")


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""
    status: str
    mock_mode: bool
    llm_provider: str
    environment: str
    gcp_project: str
    uptime_sec: float


class MetricsResponse(BaseModel):
    """Response schema for platform metrics endpoint."""
    total_logs_processed: int
    receipts_parsed: int
    chat_messages_exchanged: int
    total_carbon_logged_kg: float
    api_status: str


class CarbonLogEntry(BaseModel):
    """Schema for a single carbon log entry."""
    category: str
    subcategory: str
    quantity: float
    unit: str
    description: str
    carbon_kg: float
    explanation: str = ""


class TextLogResponse(BaseModel):
    """Response schema for text log submission."""
    status: str
    input_text: str
    logs: List[Dict[str, Any]]


class LogsSummaryResponse(BaseModel):
    """Response schema for user logs retrieval."""
    logs: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ChatResponse(BaseModel):
    """Response schema for Eco-Coach chat."""
    reply: str
    session_id: str
    tips_referenced: List[str]


class TipsResponse(BaseModel):
    """Response schema for green tips."""
    tips: List[str]


class InsightsResponse(BaseModel):
    """Response schema for personalized carbon insights."""
    total_carbon_kg: float
    category_breakdown: Dict[str, float]
    highest_impact_category: str
    comparative_context: Dict[str, Any]
    reduction_suggestions: List[str]


# --- API ENDPOINTS ---

@app.get("/", response_model=Dict[str, str])
async def read_root() -> Dict[str, str]:
    """Root endpoint returning API welcome message."""
    return {
        "message": "Welcome to EcoSphere AI API",
        "status": "operational",
        "documentation": "/docs",
    }


@app.get("/api", response_model=Dict[str, str])
@app.get("/api/", response_model=Dict[str, str])
async def api_root() -> Dict[str, str]:
    """API gateway root."""
    return {
        "message": "EcoSphere AI API Gateway",
        "status": "operational",
    }


@app.get("/health", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Standard health check endpoint."""
    if gemini_service.client:
        llm_provider = "gemini"
    elif gemini_service.groq_client:
        llm_provider = "groq"
    else:
        llm_provider = "mock"

    return HealthResponse(
        status="healthy",
        mock_mode=settings.USE_MOCK_SERVICES,
        llm_provider=llm_provider,
        environment=settings.ENV,
        gcp_project=settings.PROJECT_ID,
        uptime_sec=round(time.time() - START_TIME, 2),
    )


@app.get("/api/metrics", status_code=status.HTTP_200_OK, response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Return platform-wide usage metrics."""
    return MetricsResponse(
        total_logs_processed=API_METRICS["total_logs_processed"],
        receipts_parsed=API_METRICS["receipts_parsed"],
        chat_messages_exchanged=API_METRICS["chat_messages_exchanged"],
        total_carbon_logged_kg=round(API_METRICS["total_carbon_logged_kg"], 2),
        api_status="operational",
    )


@app.post("/api/logs/text", status_code=status.HTTP_201_CREATED, response_model=TextLogResponse)
async def log_natural_language_activity(
    request: TextLogRequest,
    user_id: str = Depends(get_current_user),
) -> TextLogResponse:
    """
    Process a natural language carbon log entry.

    Parses unstructured text into structured activities, calculates carbon
    footprints via emission factors, and persists log entries to the database.
    """
    sanitized_text = sanitize_user_input(request.text)
    if not sanitized_text:
        raise HTTPException(status_code=400, detail="Empty activity description after sanitization.")

    try:
        # Call Gemini to parse into structured activities
        parsed_activities = gemini_service.parse_natural_language_log(sanitized_text)

        saved_logs: List[Dict[str, Any]] = []
        for activity in parsed_activities:
            # Save to database
            saved_log = firestore_db.save_log(user_id, activity)
            saved_logs.append(saved_log)

            # Update metrics
            API_METRICS["total_logs_processed"] += 1
            API_METRICS["total_carbon_logged_kg"] += saved_log["carbon_kg"]

        logger.info("Logged %d activities for user %s (%.2f kg CO2e total)",
                     len(saved_logs), user_id[:8], sum(l["carbon_kg"] for l in saved_logs))

        return TextLogResponse(
            status="success",
            input_text=request.text,
            logs=saved_logs,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to log text activity: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing carbon log. Please try again.",
        )


@app.post("/api/logs/receipt", status_code=status.HTTP_201_CREATED)
async def log_receipt_activity(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Upload a utility bill or grocery receipt for multimodal OCR parsing.

    Extracts carbon metadata via Gemini Flash, calculates emissions,
    and persists carbon log entries to the database.
    """
    # Validate file size at the server level
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Validate file content type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    file_mime = file.content_type or "image/jpeg"
    if file_mime not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file_mime}. Allowed: {', '.join(allowed_types)}",
        )

    try:
        # Parse receipt using Gemini Flash multimodal API
        parsed_receipt = gemini_service.parse_receipt(file_bytes, file_mime)

        merchant = parsed_receipt.get("merchant", "Receipt Upload")
        date = parsed_receipt.get("date") or time.strftime("%Y-%m-%d")

        saved_logs: List[Dict[str, Any]] = []
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
                    "explanation": f"Extracted from {merchant} receipt/bill.",
                }
                saved_log = firestore_db.save_log(user_id, log_data)
                saved_logs.append(saved_log)

                # Update metrics
                API_METRICS["total_logs_processed"] += 1
                API_METRICS["total_carbon_logged_kg"] += carbon_kg

        API_METRICS["receipts_parsed"] += 1
        logger.info("Parsed receipt from '%s' with %d carbon items for user %s",
                     merchant, len(saved_logs), user_id[:8])

        return {
            "status": "success",
            "merchant": merchant,
            "date": date,
            "total_amount": parsed_receipt.get("total_amount", 0.0),
            "is_utility_bill": parsed_receipt.get("is_utility_bill", False),
            "items": parsed_receipt.get("items", []),
            "estimated_total_carbon_kg": parsed_receipt.get("estimated_total_carbon_kg", 0.0),
            "saved_logs": saved_logs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process receipt: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error parsing receipt/bill file. Please try again.",
        )


@app.get("/api/logs", status_code=status.HTTP_200_OK, response_model=LogsSummaryResponse)
async def get_user_logs(
    user_id: str = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of logs to return."),
    offset: int = Query(default=0, ge=0, description="Number of logs to skip for pagination."),
) -> LogsSummaryResponse:
    """
    Retrieve carbon logs for the authenticated user with pagination support.
    """
    try:
        logs = firestore_db.get_logs(user_id, limit=limit, offset=offset)

        # Calculate category summaries
        summary: Dict[str, float] = {"transit": 0.0, "energy": 0.0, "food": 0.0, "waste": 0.0}
        total = 0.0
        for log in logs:
            cat = log["category"]
            carbon = log["carbon_kg"]
            if cat in summary:
                summary[cat] += carbon
            total += carbon

        return LogsSummaryResponse(
            logs=logs,
            summary={
                "categories": {k: round(v, 2) for k, v in summary.items()},
                "total_carbon_kg": round(total, 2),
            },
        )
    except Exception as e:
        logger.error("Failed to fetch logs: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve carbon log history.",
        )


@app.post("/api/chat", status_code=status.HTTP_200_OK, response_model=ChatResponse)
async def chat_with_eco_coach(
    request: ChatMessageRequest,
    user_id: str = Depends(get_current_user),
) -> ChatResponse:
    """
    Conversational Eco-Coach chatbot endpoint.

    Retrieves recent chat turns, queries vector search for matching environmental
    tips (RAG), calls Gemini to generate feedback, saves chat log, and returns
    the response.
    """
    sanitized_message = sanitize_user_input(request.message)

    try:
        # 1. Fetch recent logs to calculate user score context
        logs = firestore_db.get_logs(user_id, limit=15)
        current_score_kg = sum(log["carbon_kg"] for log in logs)

        # 2. Get recent chat history
        history = firestore_db.get_chat_history(request.session_id, limit=6)

        # 3. Firestore Vector Search for matching environmental tips (RAG)
        injected_tips = firestore_db.search_tips_rag(sanitized_message, limit=3)

        # 4. Generate chatbot response
        coach_reply = gemini_service.generate_coaching_response(
            message=sanitized_message,
            chat_history=history,
            tips=injected_tips,
            current_score_kg=round(current_score_kg, 2),
        )

        # 5. Save turns to database
        firestore_db.save_chat_turn(request.session_id, "user", sanitized_message)
        firestore_db.save_chat_turn(request.session_id, "assistant", coach_reply)

        API_METRICS["chat_messages_exchanged"] += 2
        logger.info("Chat exchange for user %s in session %s", user_id[:8], request.session_id[:12])

        return ChatResponse(
            reply=coach_reply,
            session_id=request.session_id,
            tips_referenced=injected_tips,
        )
    except Exception as e:
        logger.error("Failed to execute chat: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Eco-Coach is temporarily experiencing technical difficulties.",
        )


@app.get("/api/tips", status_code=status.HTTP_200_OK, response_model=TipsResponse)
async def get_green_tips(
    query: Optional[str] = None,
    category: Optional[str] = None,
    user_id: str = Depends(get_current_user),
) -> TipsResponse:
    """
    Retrieve personalized, semantic environmental recommendations.

    Uses Firestore Vector Search (production) or keyword matching (mock)
    to find the most relevant tips for the user's query.
    """
    try:
        query_text = sanitize_user_input(query) if query else "general green lifestyle tips"
        tips = firestore_db.search_tips_rag(query_text, category_hint=category, limit=5)
        return TipsResponse(tips=tips)
    except Exception as e:
        logger.warning("Failed to retrieve tips: %s", e)
        return TipsResponse(tips=[
            "Switch to public transport or bicycling for daily commutes.",
            "Incorporate more vegetable protein and reduce beef intake.",
            "Unplug power strips and electronic chargers when away.",
        ])


@app.get("/api/insights", status_code=status.HTTP_200_OK, response_model=InsightsResponse)
async def get_carbon_insights(
    user_id: str = Depends(get_current_user),
) -> InsightsResponse:
    """
    Return personalized carbon insights with comparative context.

    Compares the user's footprint against global and national averages,
    identifies highest-impact categories, and generates actionable reduction
    suggestions.
    """
    try:
        logs = firestore_db.get_logs(user_id, limit=100)

        # Calculate category breakdown
        breakdown: Dict[str, float] = {"transit": 0.0, "energy": 0.0, "food": 0.0, "waste": 0.0}
        total = 0.0
        for log in logs:
            cat = log["category"]
            carbon = log["carbon_kg"]
            if cat in breakdown:
                breakdown[cat] += carbon
            total += carbon

        breakdown = {k: round(v, 2) for k, v in breakdown.items()}

        # Identify highest impact category
        highest_cat = max(breakdown, key=breakdown.get) if total > 0 else "food"

        # Comparative context (global averages annualized, divided to weekly for comparison)
        comparative = {
            "user_total_kg": round(total, 2),
            "global_avg_weekly_kg": 133.0,   # ~6.9 tonnes/year ÷ 52
            "india_avg_weekly_kg": 36.5,      # ~1.9 tonnes/year ÷ 52
            "eu_avg_weekly_kg": 126.9,        # ~6.6 tonnes/year ÷ 52
            "context_note": "Averages are per-capita weekly estimates (World Bank 2023).",
        }

        # Generate category-specific reduction suggestions
        suggestions_map = {
            "transit": [
                "Switch 2+ car trips per week to public transport to cut transit emissions by 40%.",
                "Consider carpooling — sharing rides halves per-person transport emissions.",
                "For trips under 3 km, walk or cycle for zero emissions and health benefits.",
            ],
            "energy": [
                "Switch to LED lighting — saves up to 85% energy per bulb.",
                "Set AC 1-2°C higher in summer for 10% HVAC energy savings.",
                "Unplug standby electronics to save 5-10% on electricity bills.",
            ],
            "food": [
                "Replace 2 meat meals per week with plant-based to cut food emissions by 25%.",
                "Buy seasonal, locally-sourced produce to minimize food transport emissions.",
                "Plan meals to reduce food waste — landfill waste generates potent methane.",
            ],
            "waste": [
                "Compost organic waste to prevent methane generation in landfills.",
                "Separate recyclables properly — recycling aluminium saves 95% of production energy.",
                "Switch to reusable bags, bottles, and containers to eliminate single-use plastic.",
            ],
        }

        return InsightsResponse(
            total_carbon_kg=round(total, 2),
            category_breakdown=breakdown,
            highest_impact_category=highest_cat,
            comparative_context=comparative,
            reduction_suggestions=suggestions_map.get(highest_cat, suggestions_map["food"]),
        )
    except Exception as e:
        logger.error("Failed to generate insights: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate carbon insights.",
        )
