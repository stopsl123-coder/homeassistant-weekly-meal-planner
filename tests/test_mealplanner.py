from __future__ import annotations

import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

COMPONENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "weekly_meal_planner"
)
PACKAGE_NAME = "weekly_meal_planner_test_package"
test_package = types.ModuleType(PACKAGE_NAME)
test_package.__path__ = [str(COMPONENT_PATH)]
sys.modules[PACKAGE_NAME] = test_package

from weekly_meal_planner_test_package.database import MealPlannerDatabase
from weekly_meal_planner_test_package.mealplanner import (
    calculate_meal_nutrition,
    calculate_week_nutrition,
    generate_shopping_list,
    generate_week_plan,
)


class MealPlannerDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "mealplanner.db")
        self.database = MealPlannerDatabase(self.database_path)
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initialization_preserves_existing_meals(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)",
                ("Legacy meal", '{"Rice":{"amount":100,"unit":"g"}}', "lunch"),
            )
            connection.commit()
        finally:
            connection.close()

        self.database.initialize()

        self.assertEqual(
            self.database.get_meal("Legacy meal"),
            {
                "name": "Legacy meal",
                "meal_type": "lunch",
                "servings": 1,
                "ingredients": {"Rice": {"amount": 100, "unit": "g"}},
            },
        )

    def test_saving_recipe_updates_same_name_without_duplicating(self) -> None:
        self.database.add_meal(
            "Rice", "lunch", 2, {"Rice": {"amount": 100, "unit": "g"}}
        )
        self.database.add_meal(
            "Rice", "dinner", 4, {"Rice": {"amount": 200, "unit": "g"}}
        )

        meals = self.database.get_meals()
        self.assertEqual(len(meals), 1)
        self.assertEqual(meals[0]["meal_type"], "dinner")
        self.assertEqual(meals[0]["servings"], 4)
        self.assertEqual(meals[0]["ingredients"]["Rice"]["amount"], 200)

    def test_week_plan_is_persisted_and_replaced_only_for_its_week(self) -> None:
        first_week = {
            "2026-10-05": {"lunch": "Soup"},
            "2026-10-06": {"dinner": "Pasta"},
        }
        next_week = {"2026-10-12": {"lunch": "Salad"}}
        self.database.replace_week_plan("2026-10-05", first_week)
        self.database.replace_week_plan("2026-10-12", next_week)

        self.assertEqual(
            self.database.get_week_plan("2026-10-05"),
            first_week,
        )
        self.database.replace_week_plan(
            "2026-10-05", {"2026-10-05": {"lunch": "Curry"}}
        )
        self.assertEqual(
            self.database.get_week_plan("2026-10-05"),
            {"2026-10-05": {"lunch": "Curry"}},
        )
        self.assertEqual(self.database.get_week_plan("2026-10-12"), next_week)
        self.assertEqual(
            self.database.get_recent_meal_usage("2026-10-12"),
            {"Curry": 1},
        )

    def test_legacy_database_adds_servings_without_losing_recipe_data(self) -> None:
        legacy_path = str(Path(self.temp_dir.name) / "legacy.db")
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE meals (
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                meal_type TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO meals VALUES (?, ?, ?)",
            ("Legacy", '{"Beans":{"amount":300,"unit":"g"}}', "dinner"),
        )
        connection.commit()
        connection.close()

        legacy_database = MealPlannerDatabase(legacy_path)
        legacy_database.initialize()

        self.assertEqual(
            legacy_database.get_meal("Legacy"),
            {
                "name": "Legacy",
                "ingredients": {"Beans": {"amount": 300, "unit": "g"}},
                "meal_type": "dinner",
                "servings": 1,
            },
        )

    def test_nutrition_search_cache_keeps_selectable_food_matches(self) -> None:
        result = {
            "fdc_id": 42,
            "description": "Brown rice",
            "nutrition": {"calories": 111, "protein": 3, "fat": 1, "carbs": 23},
        }
        self.database.cache_nutrition_search("brown rice", [result])

        self.assertEqual(self.database.get_nutrition_search("BROWN RICE"), [result])
        self.assertEqual(
            self.database.get_cached_nutrition(42)["nutrition"],
            result["nutrition"],
        )

    def test_expired_nutrition_cache_is_not_used_for_recipe_selection(self) -> None:
        result = {
            "fdc_id": 42,
            "description": "Brown rice",
            "nutrition": {"calories": 111, "protein": 3, "fat": 1, "carbs": 23},
        }
        self.database.cache_nutrition_search("brown rice", [result])
        connection = sqlite3.connect(self.database_path)
        try:
            old_timestamp = (datetime.now(UTC) - timedelta(days=8)).isoformat()
            connection.execute(
                "UPDATE nutrition_cache SET cached_at = ?", (old_timestamp,)
            )
            connection.commit()
        finally:
            connection.close()

        self.assertIsNone(self.database.get_cached_nutrition(42))


class MealPlannerLogicTests(unittest.TestCase):
    def test_plan_fills_week_from_available_lunch_and_dinner_recipes(self) -> None:
        meals = [
            {"name": "Soup", "meal_type": "lunch", "ingredients": {}},
            {"name": "Pasta", "meal_type": "dinner", "ingredients": {}},
            {"name": "Curry", "meal_type": "dinner", "ingredients": {}},
        ]

        plan = generate_week_plan(meals, date(2026, 10, 5), target_kcal=2000)

        self.assertEqual(len(plan), 7)
        self.assertEqual(sum(len(day) for day in plan.values()), 14)
        self.assertEqual(plan["2026-10-05"]["lunch"], "Soup")
        self.assertIn(plan["2026-10-05"]["dinner"], {"Pasta", "Curry"})
        self.assertEqual(generate_week_plan([], date(2026, 10, 5), 2000), {})

    def test_plan_avoids_same_recipe_in_both_slots_when_falling_back(self) -> None:
        meals = [
            {"name": "Pasta", "meal_type": "dinner", "ingredients": {}},
            {"name": "Curry", "meal_type": "dinner", "ingredients": {}},
        ]

        plan = generate_week_plan(meals, date(2026, 10, 5), target_kcal=2000)

        self.assertNotEqual(
            plan["2026-10-05"]["lunch"], plan["2026-10-05"]["dinner"]
        )

    def test_plan_respects_exclusions(self) -> None:
        meals = [
            {
                "name": "Bean stew",
                "meal_type": "dinner",
                "ingredients": {"Beans": {"amount": 200, "unit": "g"}},
            },
            {
                "name": "Pasta",
                "meal_type": "dinner",
                "ingredients": {"Pasta": {"amount": 200, "unit": "g"}},
            },
        ]

        plan = generate_week_plan(
            meals,
            date(2026, 10, 5),
            target_kcal=2000,
            excluded_ingredients={"beans"},
        )

        self.assertTrue(all("Bean stew" not in day.values() for day in plan.values()))

    def test_recipe_servings_scale_nutrition_and_shopping(self) -> None:
        meal = {
            "name": "Rice",
            "meal_type": "dinner",
            "servings": 4,
            "ingredients": {
                "Rice": {
                    "amount": 400,
                    "unit": "g",
                    "nutrition_per_100g": {
                        "calories": 100,
                        "protein": 2,
                        "fat": 1,
                        "carbs": 20,
                    },
                }
            },
        }
        nutrition, missing = calculate_meal_nutrition(
            meal["ingredients"], servings=meal["servings"]
        )
        shopping = generate_shopping_list(
            {"2026-10-05": {"dinner": "Rice"}},
            [meal],
            household_servings=2,
        )

        self.assertEqual(missing, [])
        self.assertEqual(nutrition["calories"], 100)
        self.assertEqual(shopping["Rice"], {"amount": 200.0, "unit": "g"})

    def test_shopping_list_converts_units_without_mixing_dimensions(self) -> None:
        meals = [
            {
                "name": "One",
                "meal_type": "lunch",
                "ingredients": {
                    "Rice": {"amount": 500, "unit": "g"},
                    "Milk": {"amount": 500, "unit": "ml"},
                    "Eggs": {"amount": 2, "unit": "Stück"},
                },
            },
            {
                "name": "Two",
                "meal_type": "dinner",
                "ingredients": {
                    "rice": {"amount": 0.5, "unit": "kg"},
                    "milk": {"amount": 0.5, "unit": "l"},
                    "Eggs": {"amount": 1, "unit": "Stück"},
                },
            },
        ]

        shopping_list = generate_shopping_list(
            {"2026-10-05": {"lunch": "One", "dinner": "Two"}}, meals
        )

        self.assertEqual(shopping_list["Rice"], {"amount": 1000.0, "unit": "g"})
        self.assertEqual(shopping_list["Milk"], {"amount": 1000.0, "unit": "ml"})
        self.assertEqual(shopping_list["Eggs"], {"amount": 3.0, "unit": "Stück"})

    def test_shopping_list_keeps_incompatible_units_separate(self) -> None:
        meals = [
            {
                "name": "One",
                "meal_type": "lunch",
                "ingredients": {"Rice": {"amount": 100, "unit": "g"}},
            },
            {
                "name": "Two",
                "meal_type": "dinner",
                "ingredients": {"rice": {"amount": 2, "unit": "Stück"}},
            },
        ]

        shopping_list = generate_shopping_list(
            {"2026-10-05": {"lunch": "One", "dinner": "Two"}}, meals
        )

        self.assertEqual(len(shopping_list), 2)
        self.assertEqual(
            {item["unit"] for item in shopping_list.values()},
            {"g", "Stück"},
        )

    def test_nutrition_requires_weight_and_complete_nutrient_data(self) -> None:
        ingredients = {
            "Rice": {
                "amount": 200,
                "unit": "g",
                "nutrition_per_100g": {
                    "calories": 130,
                    "protein": 2.7,
                    "fat": 0.3,
                    "carbs": 28,
                },
            },
            "Milk": {
                "amount": 100,
                "unit": "ml",
                "nutrition_per_100g": {
                    "calories": 60,
                    "protein": 3,
                    "fat": 3,
                    "carbs": 5,
                },
            },
        }

        totals, missing = calculate_meal_nutrition(ingredients)

        self.assertEqual(totals["calories"], 260.0)
        self.assertEqual(missing, ["Milk"])

    def test_week_sensor_marks_incomplete_nutrition_unknown(self) -> None:
        nutrition = calculate_week_nutrition(
            {"2026-10-05": {"lunch": "Rice"}},
            [
                {
                    "name": "Rice",
                    "meal_type": "lunch",
                    "ingredients": {"Rice": {"amount": 100, "unit": "g"}},
                }
            ],
            target_kcal=2000,
        )

        self.assertIsNone(nutrition["week_total"])
        self.assertIsNone(nutrition["per_day"]["2026-10-05"])
        self.assertEqual(
            nutrition["missing_nutrition"][0]["ingredient"],
            "Rice",
        )


if __name__ == "__main__":
    unittest.main()
