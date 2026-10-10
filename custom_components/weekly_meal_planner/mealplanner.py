"""Meal planning and nutrition calculations."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

WEEKLY_TARGET_KCAL = 14_000

_MASS_UNITS = {
    "mg": 0.001,
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1_000.0,
    "lb": 453.59237,
    "lbs": 453.59237,
    "oz": 28.349523125,
}
_SHOPPING_UNITS = {
    **_MASS_UNITS,
    "ml": 1.0,
    "l": 1_000.0,
    "liter": 1_000.0,
    "litre": 1_000.0,
}


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def generate_week_plan(
    meals: list[dict[str, Any]], week_start: date
) -> dict[str, dict[str, str]]:
    """Fill this week with available lunch and dinner recipes."""
    candidates = [
        meal
        for meal in meals
        if meal["meal_type"] in {"lunch", "dinner"}
    ]
    if not candidates:
        return {}

    by_type = {
        meal_type: [meal for meal in candidates if meal["meal_type"] == meal_type]
        for meal_type in ("lunch", "dinner")
    }
    uses_shared_pool = not by_type["lunch"] or not by_type["dinner"]
    plan: dict[str, dict[str, str]] = {}
    for day_offset in range(7):
        day = (week_start + timedelta(days=day_offset)).isoformat()
        day_meals: dict[str, str] = {}
        for meal_type in ("lunch", "dinner"):
            options = by_type[meal_type] or candidates
            if options:
                index = day_offset
                if uses_shared_pool and meal_type == "dinner":
                    index += 1
                day_meals[meal_type] = options[index % len(options)]["name"]
        plan[day] = day_meals
    return plan


def calculate_meal_nutrition(
    ingredients: dict[str, dict[str, Any]],
) -> tuple[dict[str, float], list[str]]:
    """Calculate nutrients when ingredient amounts have known gram weights."""
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    missing: list[str] = []

    for name, ingredient in ingredients.items():
        unit = str(ingredient["unit"]).strip().casefold()
        grams_per_unit = _MASS_UNITS.get(unit)
        nutrition = ingredient.get("nutrition_per_100g")
        if grams_per_unit is None or not isinstance(nutrition, dict):
            missing.append(name)
            continue

        grams = float(ingredient["amount"]) * grams_per_unit
        if not all(
            isinstance(nutrition.get(key), (int, float))
            for key in totals
        ):
            missing.append(name)
            continue
        for nutrient in totals:
            totals[nutrient] += float(nutrition[nutrient]) * grams / 100

    return {key: round(value, 2) for key, value in totals.items()}, missing


def calculate_week_nutrition(
    plan: dict[str, dict[str, str]], meals: list[dict[str, Any]]
) -> dict[str, Any]:
    meals_by_name = {meal["name"]: meal for meal in meals}
    per_day: dict[str, float | None] = {}
    daily_macros: dict[str, dict[str, float] | None] = {}
    missing_nutrition: list[dict[str, str]] = []
    week_totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    week_complete = bool(plan)

    for day, day_meals in sorted(plan.items()):
        day_total = {key: 0.0 for key in week_totals}
        day_complete = True
        for meal_type, meal_name in day_meals.items():
            meal = meals_by_name.get(meal_name)
            if meal is None:
                missing_nutrition.append(
                    {"day": day, "meal": meal_name, "ingredient": "recipe not found"}
                )
                day_complete = False
                continue
            nutrients, missing = calculate_meal_nutrition(meal["ingredients"])
            for ingredient in missing:
                missing_nutrition.append(
                    {"day": day, "meal": meal_name, "ingredient": ingredient}
                )
            if missing:
                day_complete = False
                continue
            for nutrient in day_total:
                day_total[nutrient] += nutrients[nutrient]

        per_day[day] = round(day_total["calories"], 2) if day_complete else None
        daily_macros[day] = (
            {key: round(value, 2) for key, value in day_total.items()}
            if day_complete
            else None
        )
        if day_complete:
            for nutrient in week_totals:
                week_totals[nutrient] += day_total[nutrient]
        else:
            week_complete = False

    return {
        "per_day": per_day,
        "daily_macros": daily_macros,
        "week_total": round(week_totals["calories"], 2) if week_complete else None,
        "week_macros": (
            {key: round(value, 2) for key, value in week_totals.items()}
            if week_complete
            else None
        ),
        "week_target": WEEKLY_TARGET_KCAL,
        "difference": (
            round(week_totals["calories"] - WEEKLY_TARGET_KCAL, 2)
            if week_complete
            else None
        ),
        "missing_nutrition": missing_nutrition,
    }


def generate_shopping_list(
    plan: dict[str, dict[str, str]], meals: list[dict[str, Any]]
) -> dict[str, dict[str, float | str]]:
    """Combine same-unit quantities and convert compatible units safely."""
    meals_by_name = {meal["name"]: meal for meal in meals}
    totals: dict[tuple[str, str], dict[str, Any]] = {}

    for day_meals in plan.values():
        for meal_name in day_meals.values():
            meal = meals_by_name.get(meal_name)
            if meal is None:
                continue
            for ingredient_name, ingredient in meal["ingredients"].items():
                unit = str(ingredient["unit"]).strip()
                unit_key = unit.casefold()
                factor = _SHOPPING_UNITS.get(unit_key)
                if unit_key in _MASS_UNITS:
                    dimension = "mass"
                elif unit_key in {"ml", "l", "liter", "litre"}:
                    dimension = "volume"
                else:
                    dimension = unit_key
                key = (
                    ingredient_name.strip().casefold(),
                    dimension if factor is not None else unit_key,
                )
                group = totals.setdefault(
                    key,
                    {
                        "name": ingredient_name.strip(),
                        "amount": 0.0,
                        "unit": {"mass": "g", "volume": "ml"}.get(dimension, unit),
                    },
                )
                group["amount"] += float(ingredient["amount"]) * (factor or 1.0)

    shopping_list: dict[str, dict[str, float | str]] = {}
    used_names: set[str] = set()
    for group in totals.values():
        name = group["name"]
        display_name = name
        if display_name.casefold() in used_names:
            display_name = f"{name} ({group['unit']})"
        while display_name.casefold() in used_names:
            display_name = f"{display_name} (2)"
        used_names.add(display_name.casefold())
        shopping_list[display_name] = {
            "amount": round(group["amount"], 3),
            "unit": group["unit"],
        }
    return shopping_list


def build_dashboard_data(
    plan: dict[str, dict[str, str]], meals: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "plan": plan,
        "shopping_list": generate_shopping_list(plan, meals),
        "nutrition": calculate_week_nutrition(plan, meals),
    }
