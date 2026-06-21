"""
Unit tests for carbon_calc.py emission factor calculations.

Tests all category paths, edge cases, and graceful fallback behavior.
"""
import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.carbon_calc import calculate_footprint, EMISSION_FACTORS


class TestCarbonCalculations(unittest.TestCase):
    """Verify carbon calculations for all emission factor categories."""

    # --- TRANSIT TESTS ---

    def test_car_petrol_calculation(self):
        result = calculate_footprint("transit", "car_petrol", 100)
        self.assertAlmostEqual(result["carbon_kg"], 18.0, places=1)
        self.assertEqual(result["subcategory_matched"], "car_petrol")

    def test_car_diesel_calculation(self):
        result = calculate_footprint("transit", "car_diesel", 50)
        self.assertAlmostEqual(result["carbon_kg"], 8.5, places=1)

    def test_car_electric_calculation(self):
        result = calculate_footprint("transit", "car_electric", 200)
        self.assertAlmostEqual(result["carbon_kg"], 10.0, places=1)

    def test_motorbike_calculation(self):
        result = calculate_footprint("transit", "motorbike", 30)
        self.assertAlmostEqual(result["carbon_kg"], 3.0, places=1)

    def test_bus_calculation(self):
        result = calculate_footprint("transit", "bus", 25)
        self.assertAlmostEqual(result["carbon_kg"], 2.0, places=1)

    def test_train_calculation(self):
        result = calculate_footprint("transit", "train", 150)
        self.assertAlmostEqual(result["carbon_kg"], 6.0, places=1)

    def test_flight_economy_calculation(self):
        result = calculate_footprint("transit", "flight_economy", 1000)
        self.assertAlmostEqual(result["carbon_kg"], 150.0, places=0)

    def test_flight_business_calculation(self):
        result = calculate_footprint("transit", "flight_business", 1000)
        self.assertAlmostEqual(result["carbon_kg"], 290.0, places=0)

    # --- ENERGY TESTS ---

    def test_electricity_kwh_calculation(self):
        result = calculate_footprint("energy", "electricity_kwh", 100)
        self.assertAlmostEqual(result["carbon_kg"], 82.0, places=0)

    def test_natural_gas_calculation(self):
        result = calculate_footprint("energy", "natural_gas_m3", 10)
        self.assertAlmostEqual(result["carbon_kg"], 20.2, places=1)

    def test_lpg_calculation(self):
        result = calculate_footprint("energy", "lpg_kg", 14.2)
        self.assertAlmostEqual(result["carbon_kg"], 42.32, places=1)

    # --- FOOD TESTS ---

    def test_beef_calculation(self):
        result = calculate_footprint("food", "beef_kg", 1)
        self.assertAlmostEqual(result["carbon_kg"], 27.0, places=1)

    def test_vegan_meal_calculation(self):
        result = calculate_footprint("food", "meal_vegan", 3)
        self.assertAlmostEqual(result["carbon_kg"], 2.7, places=1)

    def test_standard_meal_calculation(self):
        result = calculate_footprint("food", "meal_standard", 1)
        self.assertAlmostEqual(result["carbon_kg"], 2.1, places=1)

    def test_poultry_calculation(self):
        result = calculate_footprint("food", "poultry_kg", 2)
        self.assertAlmostEqual(result["carbon_kg"], 13.8, places=1)

    # --- WASTE TESTS ---

    def test_landfill_waste_calculation(self):
        result = calculate_footprint("waste", "landfill_kg", 5)
        self.assertAlmostEqual(result["carbon_kg"], 2.6, places=1)

    def test_recycled_waste_calculation(self):
        result = calculate_footprint("waste", "recycled_kg", 10)
        self.assertAlmostEqual(result["carbon_kg"], 0.8, places=1)

    # --- EDGE CASES ---

    def test_zero_quantity_returns_zero(self):
        result = calculate_footprint("transit", "car_petrol", 0)
        self.assertEqual(result["carbon_kg"], 0.0)

    def test_fractional_quantity(self):
        result = calculate_footprint("food", "beef_kg", 0.5)
        self.assertAlmostEqual(result["carbon_kg"], 13.5, places=1)

    def test_unknown_category_returns_zero(self):
        result = calculate_footprint("swimming", "pool", 10)
        self.assertEqual(result["carbon_kg"], 0.0)
        self.assertIn("error", result)

    def test_unknown_subcategory_uses_default_fallback(self):
        """An unknown subcategory in a known category should fallback to the default factor."""
        result = calculate_footprint("transit", "unknown_vehicle", 10)
        self.assertGreater(result["carbon_kg"], 0.0)

    def test_partial_subcategory_match(self):
        """Partial key matches should work (e.g., 'petrol' matching 'car_petrol')."""
        result = calculate_footprint("transit", "petrol", 100)
        self.assertGreater(result["carbon_kg"], 0.0)

    def test_case_insensitive_category(self):
        result = calculate_footprint("TRANSIT", "car_petrol", 10)
        self.assertAlmostEqual(result["carbon_kg"], 1.8, places=1)

    def test_whitespace_trimming(self):
        result = calculate_footprint("  energy  ", "  electricity_kwh  ", 100)
        self.assertAlmostEqual(result["carbon_kg"], 82.0, places=0)

    def test_calculation_basis_string_present(self):
        result = calculate_footprint("food", "beef_kg", 2)
        self.assertIn("calculation_basis", result)
        self.assertIn("units", result["calculation_basis"])

    def test_factor_used_is_returned(self):
        result = calculate_footprint("energy", "electricity_kwh", 1)
        self.assertEqual(result["factor_used"], 0.82)

    # --- CACHING TEST ---

    def test_caching_returns_same_result(self):
        """Verify that lru_cache returns identical results for same inputs."""
        r1 = calculate_footprint("transit", "car_petrol", 50)
        r2 = calculate_footprint("transit", "car_petrol", 50)
        self.assertEqual(r1, r2)

    # --- EMISSION FACTORS INTEGRITY ---

    def test_all_categories_have_factors(self):
        """Every category in the emission factors dict should have at least one subcategory."""
        for category, factors in EMISSION_FACTORS.items():
            self.assertGreater(len(factors), 0, f"Category '{category}' has no emission factors")

    def test_all_factors_are_positive(self):
        """All emission factors must be positive numbers."""
        for category, factors in EMISSION_FACTORS.items():
            for subcategory, value in factors.items():
                self.assertGreater(value, 0, f"Factor for {category}/{subcategory} is not positive")


if __name__ == "__main__":
    unittest.main()
