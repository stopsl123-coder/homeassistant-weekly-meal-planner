from homeassistant.helpers.entity import Entity
from .mealplanner import generate_shopping_list, calculate_calories_for_meal, week_plan

WEEKLY_TARGET_KCAL = 14000

class ShoppingListSensor(Entity):
    @property
    def name(self):
        return "Weekly Meal Planner Shopping List"

    @property
    def state(self):
        return "bereit"

    @property
    def extra_state_attributes(self):
        return generate_shopping_list()

class MealCaloriesSensor(Entity):
    @property
    def name(self):
        return "Weekly Meal Planner Calories"

    @property
    def state(self):
        total = 0
        for day, meals in week_plan.items():
            for meal_type, meal_name in meals.items():
                total += calculate_calories_for_meal(meal_name)
        return round(total, 2)

    @property
    def extra_state_attributes(self):
        day_calories = {}
        total = 0
        for day, meals in week_plan.items():
            day_total = 0
            for meal_type, meal_name in meals.items():
                day_total += calculate_calories_for_meal(meal_name)
            day_calories[day] = round(day_total, 2)
            total += day_total

        return {
            "per_day": day_calories,
            "week_total": round(total, 2),
            "week_target": WEEKLY_TARGET_KCAL,
            "difference": round(total - WEEKLY_TARGET_KCAL, 2)
        }
