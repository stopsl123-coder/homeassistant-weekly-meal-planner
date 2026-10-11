"""TheMealDB recipe search client."""

from __future__ import annotations

import re
from typing import Any

import aiohttp

RECIPE_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"


async def search_recipes(
    session: aiohttp.ClientSession, query: str
) -> list[dict[str, Any]]:
    """Find recipes by name and return their ingredients and source metadata."""
    timeout = aiohttp.ClientTimeout(total=20)
    async with session.get(
        RECIPE_SEARCH_URL, params={"s": query}, timeout=timeout
    ) as response:
        response.raise_for_status()
        data = await response.json()

    return parse_recipe_response(data)


def parse_recipe_response(data: Any) -> list[dict[str, Any]]:
    """Normalize TheMealDB response for recipe search and import."""
    meals = data.get("meals") if isinstance(data, dict) else None
    if meals is None:
        return []
    if not isinstance(meals, list):
        raise ValueError("Rezeptdatenbank lieferte ungültige Suchergebnisse.")

    recipes = []
    for meal in meals:
        if not isinstance(meal, dict) or not meal.get("idMeal"):
            continue
        ingredients = []
        for index in range(1, 21):
            name = str(meal.get(f"strIngredient{index}") or "").strip()
            if not name:
                continue
            ingredients.append(
                {
                    "name": name,
                    "measure": str(meal.get(f"strMeasure{index}") or "").strip(),
                }
            )
        instructions = re.sub(
            r"\r\n?", "\n", str(meal.get("strInstructions") or "")
        ).strip()
        recipes.append(
            {
                "id": str(meal["idMeal"]),
                "name": str(meal.get("strMeal") or "").strip(),
                "category": str(meal.get("strCategory") or "").strip(),
                "area": str(meal.get("strArea") or "").strip(),
                "instructions": instructions,
                "source_url": str(meal.get("strSource") or "").strip(),
                "image_url": str(meal.get("strMealThumb") or "").strip(),
                "ingredients": ingredients,
                "source": "TheMealDB",
            }
        )
    return recipes
