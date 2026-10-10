"""Async USDA FoodData Central client."""

from __future__ import annotations

import math
from typing import Any

import aiohttp

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


async def get_nutrition_for_item(
    session: aiohttp.ClientSession, api_key: str, item_name: str
) -> dict[str, float] | None:
    """Return USDA nutrient values per 100 g for an ingredient."""
    timeout = aiohttp.ClientTimeout(total=15)
    async with session.get(
        USDA_SEARCH_URL,
        params={"api_key": api_key, "query": item_name, "pageSize": 1},
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        data = await response.json()

    if not isinstance(data, dict) or not isinstance(data.get("foods"), list):
        return None
    for food in data["foods"]:
        if not isinstance(food, dict):
            continue
        nutrition = _nutrition_from_food(food)
        if nutrition is not None:
            return nutrition
    return None


def _nutrition_from_food(food: dict[str, Any]) -> dict[str, float] | None:
    food_nutrients = food.get("foodNutrients")
    if not isinstance(food_nutrients, list):
        return None

    nutrients: dict[int | str, dict[str, Any]] = {}
    for nutrient in food_nutrients:
        if not isinstance(nutrient, dict):
            continue
        nutrient_id = nutrient.get("nutrientId")
        if nutrient_id is not None:
            nutrients[nutrient_id] = nutrient
            nutrients[str(nutrient_id)] = nutrient

    energy = nutrients.get(1008)
    if energy is None:
        energy = next(
            (
                value
                for value in nutrients.values()
                if value.get("nutrientName") == "Energy"
            ),
            None,
        )
    if energy is None or energy.get("value") is None:
        return None

    calories = float(energy["value"])
    energy_unit = str(energy.get("unitName", "")).casefold()
    if energy_unit == "kj":
        calories /= 4.184
    elif energy_unit != "kcal":
        return None
    if not math.isfinite(calories) or calories < 0:
        return None

    def nutrient_value(nutrient_id: int) -> float | None:
        nutrient = nutrients.get(nutrient_id) or nutrients.get(str(nutrient_id))
        if nutrient is None or nutrient.get("value") is None:
            return None
        value = float(nutrient["value"])
        return value if math.isfinite(value) and value >= 0 else None

    values = {
        "calories": calories,
        "protein": nutrient_value(1003),
        "fat": nutrient_value(1004),
        "carbs": nutrient_value(1005),
    }
    if any(value is None for value in values.values()):
        return None
    return {key: float(value) for key, value in values.items()}
