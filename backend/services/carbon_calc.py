"""
Carbon footprint calculation engine.

Converts activity parameters (category, subcategory, quantity) into estimated
CO2e emissions using standardized emission factors from peer-reviewed sources.

Emission factor sources:
- Transit: UK DEFRA 2023 GHG Conversion Factors
- Energy: India Central Electricity Authority (CEA) CO2 Baseline Database v18
- Food: Poore & Nemecek (2018), Science 360(6392)
- Waste: US EPA WARM Model v15
"""
from functools import lru_cache
from typing import Dict, Any, Tuple

# Standard Emission Factors (kg CO2e per unit)
EMISSION_FACTORS: Dict[str, Dict[str, float]] = {
    "transit": {
        "car_petrol": 0.18,      # per km
        "car_diesel": 0.17,      # per km
        "car_electric": 0.05,    # per km
        "motorbike": 0.10,       # per km
        "bus": 0.08,             # per passenger-km
        "train": 0.04,           # per passenger-km
        "flight_economy": 0.15,  # per passenger-km
        "flight_business": 0.29, # per passenger-km
    },
    "energy": {
        "electricity_kwh": 0.82, # per kWh (average India grid intensity)
        "natural_gas_m3": 2.02,  # per m3
        "lpg_kg": 2.98,          # per kg
    },
    "food": {
        "beef_kg": 27.0,
        "pork_kg": 7.2,
        "poultry_kg": 6.9,
        "fish_kg": 5.4,
        "dairy_kg": 13.5,
        "meal_vegan": 0.9,       # per meal
        "meal_vegetarian": 1.4,  # per meal
        "meal_meat_heavy": 3.2,  # per meal
        "meal_standard": 2.1,    # per meal
    },
    "waste": {
        "landfill_kg": 0.52,     # per kg of general waste
        "recycled_kg": 0.08,     # per kg of recycled waste
    },
}

# Default fallback factors per category
_DEFAULT_FACTORS: Dict[str, Tuple[float, str]] = {
    "transit": (0.15, "average_transit"),
    "energy": (0.82, "electricity_kwh"),
    "food": (2.1, "meal_standard"),
    "waste": (0.52, "landfill_kg"),
}


@lru_cache(maxsize=512)
def calculate_footprint(category: str, subcategory: str, quantity: float) -> Dict[str, Any]:
    """
    Calculate carbon footprint in kg CO2e for a given activity.

    Args:
        category: Activity category (transit, energy, food, waste).
        subcategory: Specific activity type within the category.
        quantity: Numerical amount (km, kWh, kg, meals, etc.).

    Returns:
        Dictionary containing carbon_kg, factor_used, subcategory_matched,
        and a human-readable calculation_basis string.
    """
    category = category.lower().strip()
    subcategory = subcategory.lower().strip()

    if category not in EMISSION_FACTORS:
        return {
            "carbon_kg": 0.0,
            "error": f"Unknown category: {category}",
            "calculation_basis": "Unknown category",
        }

    factors = EMISSION_FACTORS[category]
    factor = factors.get(subcategory)
    matched_subcategory = subcategory

    # Graceful fallback if subcategory isn't exact
    if factor is None:
        # Try to find a partial match
        for key, val in factors.items():
            if key in subcategory or subcategory in key:
                factor = val
                matched_subcategory = key
                break

        # Default fallback factor if still none
        if factor is None and category in _DEFAULT_FACTORS:
            factor, matched_subcategory = _DEFAULT_FACTORS[category]

    if factor is None:
        return {
            "carbon_kg": 0.0,
            "error": f"No emission factor found for {category}/{subcategory}",
            "calculation_basis": "No matching emission factor",
        }

    carbon = round(quantity * factor, 2)

    return {
        "carbon_kg": carbon,
        "factor_used": factor,
        "subcategory_matched": matched_subcategory,
        "calculation_basis": f"{quantity} units × {factor} kg CO2e/unit ({matched_subcategory})",
    }
