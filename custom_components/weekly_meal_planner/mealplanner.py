from .database import get_ingredients

week_plan = {}

def generate_shopping_list():
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
    return shopping_list

def calculate_calories_for_meal(meal_name):
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
