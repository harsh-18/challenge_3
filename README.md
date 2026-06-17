# EcoSphere AI - Carbon Footprint Awareness Platform (Challenge 3)

EcoSphere AI is a premium, self-contained AI-powered platform designed to help individuals track, understand, and reduce their carbon footprint. By combining unstructured natural language processing, multimodal receipt OCR parsing, and a personalized AI Eco-Coach, the platform makes sustainability actionable.

---

## 🔗 Production Deployments

*   **EcoSphere AI Web App (Frontend)**: [https://genai-apac-2-497615.web.app](https://genai-apac-2-497615.web.app, https://ecosphere-ai-app.web.app/)
*   **FastAPI Backend Gateway**: [https://ecosphere-backend-258208842022.us-central1.run.app](https://ecosphere-backend-258208842022.us-central1.run.app)
*   **Health Status Endpoint**: [https://ecosphere-backend-258208842022.us-central1.run.app/health](https://ecosphere-backend-258208842022.us-central1.run.app/health)
*   **Reverse Proxy Gateway Base Route**: [https://genai-apac-2-497615.web.app/api/](https://genai-apac-2-497615.web.app/api/)

---

## 🏗️ Google Cloud & Firebase Integration Architecture

EcoSphere AI utilizes an integrated suite of Google Cloud services to maintain low latency, serverless scalability, and state-of-the-art security:

1.  **Vertex AI (Gemini Models)**:
    *   **Gemini 1.5 Pro**: Parses complex, unstructured carbon logging statements (e.g. *"I drove 45 km in a diesel car and flew economy from Delhi to Mumbai"*) and returns structured parameters for carbon emissions calculations.
    *   **Gemini 1.5 Flash**: Performs fast multimodal OCR parsing on utility bills and grocery store receipts (JPEG/PNG/PDF), extracting pricing, consumption (e.g. kWh), and merchant details.
    *   **text-embedding-004**: Generates 768-dimensional text embeddings for environmental recommendations.
2.  **Cloud Firestore (Native Vector Search)**:
    *   Stores carbon logs and user profiles.
    *   Uses **Firestore Native Vector Search** (`find_nearest`) to execute real-time cosine similarity search over environmental tips. This enables semantic **RAG (Retrieval-Augmented Generation)** inside the Eco-Coach chat without requiring a third-party vector database.
3.  **Google Cloud Run**:
    *   Hosts the FastAPI containerized backend. Automatically scales down to zero when idle and securely mounts production secrets.
4.  **Firebase Hosting**:
    *   Distributes the static React/Vite frontend. Features custom `Cache-Control` header overrides to prevent browser caching of HTML bundles (avoiding stale JS script references) and handles reverse-proxy `/api/**` routing to bypass CORS.
5.  **Google Cloud Secret Manager**:
    *   Stores the `GEMINI_API_KEY` securely as a secret, mounting it directly into the Cloud Run container runtime environment.

---

## 🛠️ Local Installation & Development

### 1. Backend Setup
1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Start the local development server:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```
    *Note: The backend defaults to `USE_MOCK_SERVICES=true` locally if GCP credentials/keys are missing, enabling fully functional offline sandbox testing.*

### 2. Database Seeding (Firestore RAG)
To populate Firestore with the environmental recommendations and their respective Gemini vector embeddings:
```bash
# Set your environment variables
$env:GEMINI_API_KEY="your_gemini_api_key"
$env:PROJECT_ID="genai-apac-2-497615"
$env:USE_MOCK_SERVICES="false"

# Run the seeding script
python backend/seed_tips.py
```

### 3. Frontend Setup
1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the Vite local development server:
    ```bash
    npm run dev
    ```
    *Open `http://localhost:3000` to access the application. Vite is configured to proxy all `/api` calls directly to `http://localhost:8000` to bypass CORS issues locally.*

---

## 🚀 Cloud Deployment Commands

### Backend Deployment (Google Cloud Run)
```powershell
gcloud run deploy ecosphere-backend `
  --source ./backend `
  --region us-central1 `
  --allow-unauthenticated `
  --set-env-vars="ENV=production,PROJECT_ID=genai-apac-2-497615,USE_MOCK_SERVICES=false" `
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"
```

### Frontend Deployment (Firebase Hosting)
```powershell
# Build Vite production assets
cd frontend
npm run build
cd ..

# Deploy to Hosting
npx firebase-tools deploy --only hosting --project genai-apac-2-497615
```

---

## 🔒 Security Design
1.  **Zero Hardcoded Secrets**: Production keys are mounted exclusively via Cloud Secret Manager at runtime.
2.  **Reverse Proxy Rewrite API**: Firebase Hosting reverse-proxies the `/api/**` URL mapping directly to Cloud Run, preventing CORS issues and making client configurations simple.
3.  **Strict Caching Policies**: Global headers block local caching of `index.html` on the CDN level, forcing the browser to fetch fresh assets on redeploys.
