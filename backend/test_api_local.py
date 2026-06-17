import unittest
import sys
import os

# Add parent directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

class TestEcoSphereAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer mock-user-123"}

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("mock_mode", data)

    def test_get_metrics(self):
        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["api_status"], "operational")

    def test_log_natural_language_activity(self):
        payload = {"text": "I drove 25 km today and had a vegan dinner."}
        response = self.client.post("/api/logs/text", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["logs"]) > 0)
        
        # Verify carbon calculations are returned
        for log in data["logs"]:
            self.assertIn("carbon_kg", log)
            self.assertIn("category", log)

    def test_get_logs(self):
        response = self.client.get("/api/logs", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("logs", data)
        self.assertIn("summary", data)

    def test_chat_with_eco_coach(self):
        payload = {
            "message": "Hi Eco-Coach! Give me tips on travel.",
            "session_id": "test-session-1"
        }
        response = self.client.post("/api/chat", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("tips_referenced", data)

    def test_get_green_tips(self):
        response = self.client.get("/api/tips", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tips", data)
        self.assertTrue(len(data["tips"]) > 0)

    def test_unauthorized_access_defaults_gracefully(self):
        # The auth dependency should gracefully handle missing headers by defaulting to mock user
        response = self.client.get("/api/logs")
        self.assertEqual(response.status_code, 200)

    def test_empty_payload_validation(self):
        # Empty text field
        payload = {"text": ""}
        response = self.client.post("/api/logs/text", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 422)

    def test_extremely_long_payload_validation(self):
        # Payload greater than 1000 characters
        payload = {"text": "A" * 1005}
        response = self.client.post("/api/logs/text", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 422)

    def test_receipt_ocr_mock(self):
        # Upload a dummy file
        dummy_file = b"Dummy receipt content for testing."
        response = self.client.post(
            "/api/logs/receipt",
            files={"file": ("receipt.png", dummy_file, "image/png")},
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("merchant", data)
        self.assertIn("estimated_total_carbon_kg", data)

if __name__ == "__main__":
    unittest.main()
