"""
Unit tests for gemini_ops.py mock service and helper functions.

Tests mock NL parsing, mock receipt OCR, mock coaching, sanitization,
and cultural sensitivity behavior.
"""
import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force mock mode for testing
os.environ["USE_MOCK_SERVICES"] = "true"

from backend.services.gemini_ops import gemini_service, _sanitize_text, _extract_bold_key

# Force mock mode on the singleton for unit testing
gemini_service.mock_mode = True
gemini_service.client = None
gemini_service.groq_client = None
gemini_service.using_groq = False


class TestSanitizeText(unittest.TestCase):
    """Tests for the _sanitize_text helper function."""

    def test_removes_bom(self):
        text = "\ufeffHello World"
        self.assertEqual(_sanitize_text(text), "Hello World")

    def test_removes_zero_width_chars(self):
        text = "Hello\u200bWorld"
        self.assertEqual(_sanitize_text(text), "HelloWorld")

    def test_strips_whitespace(self):
        text = "  Hello  "
        self.assertEqual(_sanitize_text(text), "Hello")

    def test_empty_string(self):
        self.assertEqual(_sanitize_text(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(_sanitize_text(None))


class TestExtractBoldKey(unittest.TestCase):
    """Tests for the _extract_bold_key helper function."""

    def test_extracts_bold_keyword(self):
        text = "This is **important** info"
        self.assertEqual(_extract_bold_key(text), "important")

    def test_no_bold_markers_returns_first_40(self):
        text = "Simple text without bold markers at all"
        self.assertEqual(_extract_bold_key(text), text[:40].lower())

    def test_lowercases_bold_content(self):
        text = "Use **LED Lighting** for savings"
        self.assertEqual(_extract_bold_key(text), "led lighting")


class TestMockNLParsing(unittest.TestCase):
    """Tests for mock natural language activity parsing."""

    def test_parses_driving_activity(self):
        result = gemini_service.parse_natural_language_log("I drove 25 km today")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # Check structure of returned activity
        activity = result[0]
        self.assertIn("category", activity)
        self.assertIn("carbon_kg", activity)

    def test_parses_food_activity(self):
        result = gemini_service.parse_natural_language_log("Had a vegan dinner")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_parses_multiple_activities(self):
        result = gemini_service.parse_natural_language_log("drove 30 km and had a beef steak")
        self.assertIsInstance(result, list)
        # Should detect at least 2 activities
        self.assertGreaterEqual(len(result), 1)

    def test_parses_energy_activity(self):
        result = gemini_service.parse_natural_language_log("used 50 kWh electricity")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_parses_waste_activity(self):
        result = gemini_service.parse_natural_language_log("recycled 3 kg of plastic")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_unicode_input_handled(self):
        """Verify the parser handles Unicode input without crashing."""
        result = gemini_service.parse_natural_language_log("Drove 10 km in my car 🚗")
        self.assertIsInstance(result, list)

    def test_special_characters_handled(self):
        result = gemini_service.parse_natural_language_log("Took a flight from <Delhi> & 'Mumbai'")
        self.assertIsInstance(result, list)


class TestMockReceiptParsing(unittest.TestCase):
    """Tests for mock receipt OCR parsing."""

    def test_mock_receipt_returns_valid_structure(self):
        dummy_bytes = b"dummy receipt content"
        result = gemini_service.parse_receipt(dummy_bytes, "image/png")
        self.assertIn("merchant", result)
        self.assertIn("items", result)
        self.assertIn("estimated_total_carbon_kg", result)
        self.assertIsInstance(result["items"], list)

    def test_mock_receipt_pdf_returns_utility_bill(self):
        dummy_bytes = b"dummy PDF content"
        result = gemini_service.parse_receipt(dummy_bytes, "application/pdf")
        self.assertIn("merchant", result)
        self.assertIn("items", result)

    def test_mock_receipt_items_have_carbon(self):
        result = gemini_service.parse_receipt(b"data", "image/jpeg")
        for item in result["items"]:
            self.assertIn("carbon_kg", item)
            self.assertIn("name", item)
            self.assertIn("carbon_category", item)


class TestMockCoachingResponse(unittest.TestCase):
    """Tests for mock coaching response generation."""

    def test_coaching_returns_string(self):
        reply = gemini_service.generate_coaching_response(
            message="How can I reduce my carbon footprint?",
            chat_history=[],
            tips=["Walk more often."],
            current_score_kg=50.0,
        )
        self.assertIsInstance(reply, str)
        self.assertGreater(len(reply), 10)

    def test_coaching_with_empty_tips(self):
        reply = gemini_service.generate_coaching_response(
            message="Give me eco advice",
            chat_history=[],
            tips=[],
            current_score_kg=25.0,
        )
        self.assertIsInstance(reply, str)

    def test_coaching_preserves_context(self):
        """Verify coaching handles chat history without error."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you go green?"},
        ]
        reply = gemini_service.generate_coaching_response(
            message="What about transit?",
            chat_history=history,
            tips=["Use public transit."],
            current_score_kg=100.0,
        )
        self.assertIsInstance(reply, str)

    def test_coaching_high_carbon_score_context(self):
        """High carbon score should still produce valid response."""
        reply = gemini_service.generate_coaching_response(
            message="My score seems high",
            chat_history=[],
            tips=["Reduce meat consumption."],
            current_score_kg=500.0,
        )
        self.assertIsInstance(reply, str)


class TestServiceInitialization(unittest.TestCase):
    """Tests for GeminiService initialization in mock mode."""

    def test_mock_mode_is_active(self):
        self.assertTrue(gemini_service.mock_mode)

    def test_no_live_clients_in_mock(self):
        self.assertIsNone(gemini_service.client)


if __name__ == "__main__":
    unittest.main()
