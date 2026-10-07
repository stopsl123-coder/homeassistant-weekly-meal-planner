from .database import get_meals
from .mealplanner import calculate_calories_for_meal

DAILY_TARGET_KCAL = 2000

def generate_simple_week_plan():
    meals = get_meals()
    lunch_dinner = [m for m in meals if m["meal_type"] in ["lunch", "dinner"]]

    week_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    new_plan = {}

    idx = 0
    for day in week_days:
        day_total = 0
        day_meals = {"breakfast": "Rührei mit Toast"}

        if idx < len(lunch_dinner):
            meal_lunch = lunch_dinner[idx]["name"]
            kcal_lunch = calculate_calories_for_meal(meal_lunch)
            day_meals["lunch"] = meal_lunch
            day_total += kcal_lunch
            idx += 1

        if idx < len(lunch_dinner):
            meal_dinner = lunch_dinner[idx]["name"]
            kcal_dinner = calculate_calories_for_meal(meal_dinner)
            if day_total + kcal_dinner <= DAILY_TARGET_KCAL * 1.3:
                day_meals["dinner"] = meal_dinner
                day_total += kcal_dinner
                idx += 1
            else:
                day_meals["dinner"] = "Gemüsepfanne"

        new_plan[day] = day_meals

    return new_plan
