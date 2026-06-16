import os
import sys
from google.cloud import firestore
from google import genai

# Add backend directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(current_dir))

from backend.config import settings

# State list of environmental tips to seed
TIPS = [
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

def seed():
    project_id = os.getenv("PROJECT_ID") or settings.PROJECT_ID
    database_id = os.getenv("FIRESTORE_DATABASE") or settings.FIRESTORE_DATABASE or "(default)"
    
    print(f"Initializing Firestore client for project '{project_id}' and database '{database_id}'...")
    db = firestore.Client(project=project_id, database=database_id)
    
    api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        print("No GEMINI_API_KEY found. Using Vertex AI / Application Default Credentials...")
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
    
    print(f"Seeding {len(TIPS)} tips into Firestore collection 'environmental_tips'...")
    
    # Check if collection is already seeded
    tips_ref = db.collection("environmental_tips")
    existing_docs = list(tips_ref.limit(5).stream())
    if existing_docs:
        print("Note: Firestore 'environmental_tips' collection already has data. Appending/updating...")

    import time

    for i, tip in enumerate(TIPS, 1):
        print(f"[{i}/{len(TIPS)}] Generating embedding for: '{tip['tip_text'][:40]}...'")
        
        # Retry logic for rate limiting
        retries = 5
        delay = 10
        embedding_vector = None
        
        for attempt in range(retries):
            try:
                response = client.models.embed_content(
                    model='text-embedding-004',
                    contents=tip["tip_text"]
                )
                embedding_vector = response.embeddings[0].values
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                    print(f"  Rate limit hit. Waiting {delay}s and retrying (attempt {attempt+1}/{retries})...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"Failed to generate embedding for tip '{tip['tip_text']}': {e}")
                    sys.exit(1)
                    
        if not embedding_vector:
            print(f"Failed to generate embedding for tip after {retries} retries.")
            sys.exit(1)
            
        try:
            # Save to Firestore
            doc_ref = tips_ref.document()
            doc_ref.set({
                "category": tip["category"],
                "tip_text": tip["tip_text"],
                "embedding": embedding_vector
            })
        except Exception as e:
            print(f"Failed to save to Firestore: {e}")
            sys.exit(1)
            
    print("Firestore seeding completed successfully!")

if __name__ == "__main__":
    seed()
