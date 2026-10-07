from .database import get_meals
from .mealplanner import calculate_calories_for_meal

DAILY_TARGET_KCAL = 2000

def generate_simple_week_plan():
    meals = get_meals()
    lunch_dinner = [m for m in meals if m["meal_type"] in ["lunch", "dinner"]]
    week_days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    new_plan = {}
    idx = 0

    for day in week_days:
        day_total = 0
        day_meals = {"breakfast": "Rührei mit Toast"}

        if idx < len(lunch_dinner):
            lunch = lunch_dinner[idx]["name"]
            day_meals["lunch"] = lunch
            day_total += calculate_calories_for_meal(lunch)
            idx += 1

        if idx < len(lunch_dinner):
            dinner = lunch_dinner[idx]["name"]
            kcal = calculate_calories_for_meal(dinner)
            if day_total + kcal <= DAILY_TARGET_KCAL * 1.3:
                day_meals["dinner"] = dinner
                idx += 1
            else:
                day_meals["dinner"] = "Gemüsepfanne"

        new_plan[day] = day_meals

    return new_plan
