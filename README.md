# EcoSphere AI - Carbon Footprint Awareness Platform

Welcome to the **EcoSphere AI** workspace for Challenge 3. This project is a separate, self-contained implementation designed to help individuals understand, track, and reduce their carbon footprint using natural language logging, multimodal receipt parsing, and personalized AI coaching.

---

## 1. Google Services Integration Architecture
To make this platform secure, modern, and highly scalable, we leverage a suite of integrated Google services:

* **Vertex AI (Gemini 1.5 Flash & Pro)**:
  * *Gemini 1.5 Flash*: Used for fast conversational responses (Eco-Coach) and structured OCR parsing of uploaded electricity bills or grocery receipts.
  * *Gemini 1.5 Pro*: Used for complex carbon estimation calculations based on unstructured user inputs (e.g., "I flew economy from Delhi to Mumbai and ate two beef tacos").
* **Cloud Firestore (with Native Vector Search)**:
  * Stores user carbon logs, profile data, and conversation history.
  * Uses Firestore's **native vector search capability** to power the semantic RAG (Retrieval-Augmented Generation) search for environmental tips without needing a separate vector database.
* **Firebase Authentication**:
  * Provides secure, developer-friendly authentication (Email/Password & Google Sign-In) with JWT tokens validated by our backend.
* **Google Cloud Secret Manager**:
  * Securely stores Gemini API keys, Firebase credentials, and other sensitive secrets, injecting them into the runtime environment.
* **Google Cloud Run**:
  * Hosts the serverless FastAPI backend, offering auto-scaling, HTTPS endpoints by default, and high concurrency.
* **Firebase Hosting**:
  * Globally distributes the React/Vite web frontend over CDN with SSL enabled out of the box.
* **Cloud Storage**:
  * Secure bucket storage for user-uploaded documents (receipts, utility bills) before processing.
* **Google Maps Routes API (Optional)**:
  * Dynamically calculates precise distance and transit mode details for accurate transit carbon calculations.

---

## 2. Directory Structure
All Challenge 3 code is contained within this directory:

```
challenge_3/
├── README.md              # Project overview (this file)
├── backend/               # FastAPI backend
│   ├── main.py            # FastAPI entry point
│   ├── requirements.txt   # Backend Python dependencies
│   ├── config.py          # Secure environment configuration loading Secret Manager
│   ├── services/
│   │   ├── carbon_calc.py # Footprint calculation logic
│   │   ├── gemini_ops.py  # Gemini API operations (chat, multimodal OCR)
│   │   └── firestore_db.py# Firestore interactions & native vector search
│   └── Dockerfile         # Multi-stage container build for Cloud Run
└── frontend/              # React + Vite + Tailwind/Vanilla CSS
    ├── package.json       # Frontend dependencies
    ├── src/
    │   ├── components/    # Reusable UI elements (Charts, Chat, Upload)
    │   ├── pages/         # Dashboard, Login, Eco-Coach Chat
    │   └── firebase.js    # Firebase Auth configuration
    └── vite.config.js     # Vite configuration
```

---

## 3. Security Design
1. **Zero Hardcoded Secrets**: All keys are fetched from Google Cloud Secret Manager or local `.env` (excluded from git).
2. **Authenticated APIs**: FastAPI routes are protected by a middleware that verifies JWT identity tokens minted by Firebase Authentication.
3. **IAM Roles**: The Cloud Run service operates under a custom service account with minimal IAM permissions (strictly Firestore read/write, Secret Manager secret accessor, and Vertex AI user).
