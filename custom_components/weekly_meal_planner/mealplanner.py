import logging
from .database import get_ingredients

_LOGGER = logging.getLogger(__name__)

# Wochenplan-Datenstruktur
week_plan = {}

def add_meal(meal_name, day):
    """Fügt ein Gericht zum Wochenplan hinzu."""
    if day not in week_plan:
        week_plan[day] = {}

    # Standard: breakfast, lunch, dinner automatisch füllen
    # Du kannst das später erweitern
    if "breakfast" not in week_plan[day]:
        week_plan[day]["breakfast"] = meal_name
    elif "lunch" not in week_plan[day]:
        week_plan[day]["lunch"] = meal_name
    else:
        week_plan[day]["dinner"] = meal_name

    _LOGGER.info(f"Meal '{meal_name}' added for {day}. Current plan: {week_plan}")

def generate_week_plan():
    """Erstellt einen einfachen Wochenplan (Platzhalter)."""
    _LOGGER.info("Week plan generated.")
    return week_plan

def generate_shopping_list():
    """Generiert die Einkaufsliste basierend auf dem Wochenplan."""
    shopping_list = {}
    for day, meals in week_plan.items():
        for meal_type, meal_name in meals.items():
            ingredients = get_ingredients(meal_name)
            for item, data in ingredients.items():
                amount = data["amount"]
                unit = data["unit"]
                if item not in shopping_list:
                    shopping_list[item] = {"amount": amount, "unit": unit}
                else:
                    shopping_list[item]["amount"] += amount
    _LOGGER.info(f"Shopping list generated: {shopping_list}")
    return shopping_list

def calculate_calories_for_meal(meal_name):
    """Berechnet die Kalorien eines Gerichts."""
    ingredients = get_ingredients(meal_name)
    total = 0
    for item, data in ingredients.items():
        amount = data["amount"]
        unit = data["unit"]
        calories = data.get("calories", 0)
        if unit in ["g", "ml"]:
            total += (calories / 100) * amount
        else:
            total += calories * amount
    return round(total, 2)
