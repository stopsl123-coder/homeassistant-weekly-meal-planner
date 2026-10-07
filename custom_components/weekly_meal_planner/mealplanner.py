from .database import get_ingredients

week_plan = {
    "monday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "tuesday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "wednesday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "thursday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "friday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "saturday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "sunday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"}
}

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
                    if shopping_list[item]["unit"] == unit:
                        shopping_list[item]["amount"] += amount
                    else:
                        key = item + f" ({unit})"
                        if key not in shopping_list:
                            shopping_list[key] = {"amount": amount, "unit": unit}
                        else:
                            shopping_list[key]["amount"] += amount

    return shopping_list

def calculate_calories_for_meal(meal_name):
    ingredients = get_ingredients(meal_name)
    total_calories = 0

    for item, data in ingredients.items():
        amount = data["amount"]
        unit = data["unit"]
        calories = data.get("calories", 0)

        if unit in ["g", "ml"]:
            total_calories += (calories / 100) * amount
        elif unit == "Stück":
            total_calories += calories * amount

    return round(total_calories, 2)
