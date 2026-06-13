from typing import Dict, Any

# Standard Emission Factors (kg CO2e per unit)
EMISSION_FACTORS = {
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
        "natural_gas_m3": 2.02,   # per m3
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
    }
}

def calculate_footprint(category: str, subcategory: str, quantity: float) -> Dict[str, Any]:
    """
    Calculates carbon footprint in kg CO2e.
    """
    category = category.lower()
    subcategory = subcategory.lower()
    
    if category not in EMISSION_FACTORS:
        return {
            "carbon_kg": 0.0,
            "error": f"Unknown category: {category}",
            "calculation_basis": "Unknown category"
        }
        
    factors = EMISSION_FACTORS[category]
    factor = factors.get(subcategory)
    
    # Graceful fallback if subcategory isn't exact
    if factor is None:
        # Try to find a partial match
        for key, val in factors.items():
            if key in subcategory or subcategory in key:
                factor = val
                subcategory = key
                break
        
        # Default fallback factor if still none
        if factor is None:
            if category == "transit":
                factor = 0.15 # average km
                subcategory = "average_transit"
            elif category == "energy":
                factor = 0.82
                subcategory = "electricity_kwh"
            elif category == "food":
                factor = 2.1
                subcategory = "meal_standard"
            elif category == "waste":
                factor = 0.52
                subcategory = "landfill_kg"

    carbon = quantity * factor
    
    return {
        "carbon_kg": round(carbon, 2),
        "factor_used": factor,
        "subcategory_matched": subcategory,
        "calculation_basis": f"{quantity} units * {factor} kg CO2e/unit ({subcategory})"
    }
