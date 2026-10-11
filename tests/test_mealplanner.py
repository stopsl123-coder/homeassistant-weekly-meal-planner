from __future__ import annotations

import asyncio
import sqlite3
import io
import sys
import tempfile
import types
import unittest
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

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
from weekly_meal_planner_test_package.bls import parse_bls_archive
from weekly_meal_planner_test_package.mealplanner import (
    build_dashboard_data,
    calculate_meal_nutrition,
    calculate_week_nutrition,
    generate_shopping_list,
    generate_week_plan,
)
from weekly_meal_planner_test_package.recipe_api import (
    parse_wikibooks_recipe,
    search_recipes,
)


def _minimal_bls_archive() -> bytes:
    shared_strings = [
        "BLS Code",
        "Lebensmittelbezeichnung",
        "Food name",
        "C131000",
        "Haferflocken",
        "Oat flakes",
    ]
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{escape(value)}</t></si>" for value in shared_strings)
        + "</sst>"
    )
    worksheet_xml = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData>
  <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>
   <c r="C1" t="s"><v>2</v></c></row>
  <row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c>
   <c r="C2" t="s"><v>5</v></c><c r="G2"><v>348</v></c>
   <c r="M2"><v>13.22</v></c><c r="P2"><v>6.65</v></c>
   <c r="S2"><v>58.7</v></c></row>
 </sheetData>
</worksheet>"""
    workbook_xml = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="BLS" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    relationships_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="worksheets/sheet1.xml"/>
</Relationships>"""

    workbook_buffer = io.BytesIO()
    with zipfile.ZipFile(workbook_buffer, "w") as workbook:
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", relationships_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr(
            "BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx",
            workbook_buffer.getvalue(),
        )
    return archive_buffer.getvalue()


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
                "instructions": "",
                "source_url": "",
                "source_name": "",
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

    def test_recipe_details_and_source_are_persisted(self) -> None:
        self.database.add_meal(
            "Linsencurry",
            "dinner",
            4,
            {"Linsen": {"amount": 300, "unit": "g"}},
            "Linsen garen.",
            "https://example.org/linsencurry",
            "Wikibooks Kochbuch",
        )

        meal = self.database.get_meal("Linsencurry")

        self.assertEqual(meal["instructions"], "Linsen garen.")
        self.assertEqual(meal["source_url"], "https://example.org/linsencurry")
        self.assertEqual(
            meal["source_name"], "Wikibooks Kochbuch"
        )

    def test_deleting_recipe_removes_it_from_saved_plans(self) -> None:
        self.database.add_meal(
            "Soup", "lunch", 1, {"Beans": {"amount": 100, "unit": "g"}}
        )
        self.database.set_planned_meal("2026-10-05", "lunch", "Soup")

        self.assertTrue(self.database.delete_meal("Soup"))
        self.assertIsNone(self.database.get_meal("Soup"))
        self.assertEqual(self.database.get_week_plan("2026-10-05"), {})
        self.assertFalse(self.database.delete_meal("Soup"))

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

    def test_planned_meal_can_be_replaced_for_one_day(self) -> None:
        self.database.replace_week_plan(
            "2026-10-05",
            {"2026-10-05": {"lunch": "Soup", "dinner": "Curry"}},
        )

        self.assertTrue(
            self.database.set_planned_meal("2026-10-05", "lunch", "Salad")
        )
        self.assertTrue(
            self.database.set_planned_meal("2026-10-06", "lunch", "Salad")
        )
        self.assertEqual(
            self.database.get_week_plan("2026-10-05"),
            {
                "2026-10-05": {"lunch": "Salad", "dinner": "Curry"},
                "2026-10-06": {"lunch": "Salad"},
            },
        )

    def test_shopping_progress_is_saved_per_week_and_pruned(self) -> None:
        items = {
            "Beans": {"amount": 200.0, "unit": "g"},
            "Rice": {"amount": 100.0, "unit": "g"},
        }
        self.database.set_shopping_item(
            "2026-10-05", "Beans", True, 200.0, "g"
        )
        self.database.set_shopping_item(
            "2026-10-12", "Beans", True, 200.0, "g"
        )

        self.assertEqual(
            self.database.sync_shopping_progress("2026-10-05", items),
            {"Beans": True},
        )
        changed_items = {
            "Beans": {"amount": 250.0, "unit": "g"},
            "Rice": {"amount": 100.0, "unit": "g"},
        }
        self.assertEqual(
            self.database.sync_shopping_progress("2026-10-05", changed_items),
            {},
        )
        self.database.set_shopping_item(
            "2026-10-05", "Beans", False, 250.0, "g"
        )

        self.assertEqual(
            self.database.sync_shopping_progress("2026-10-05", changed_items),
            {},
        )
        self.assertEqual(
            self.database.sync_shopping_progress(
                "2026-10-12", {"Beans": items["Beans"]}
            ),
            {"Beans": True},
        )
        self.assertEqual(
            self.database.sync_shopping_progress("2026-10-12", {}),
            {},
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
                "instructions": "",
                "source_url": "",
                "source_name": "",
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

    def test_bls_archive_parser_reads_german_food_and_nutrients(self) -> None:
        self.assertEqual(
            list(parse_bls_archive(_minimal_bls_archive())),
            [
                {
                    "code": "C131000",
                    "name": "Haferflocken",
                    "name_en": "Oat flakes",
                    "calories": 348.0,
                    "protein": 13.22,
                    "fat": 6.65,
                    "carbs": 58.7,
                }
            ],
        )

    def test_incomplete_bls_import_keeps_existing_foods(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO bls_foods
                    (code, name, name_en, calories, protein, fat, carbs)
                VALUES ('C131000', 'Haferflocken', 'Oat flakes', 348, 13.22, 6.65, 58.7)
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(sqlite3.DatabaseError, "BLS-Import unvollständig"):
            self.database.import_bls_archive(_minimal_bls_archive())

        self.assertTrue(self.database.has_bls_data())
        self.assertEqual(
            self.database.search_bls_foods("oat")[0]["bls_code"], "C131000"
        )

    def test_bls_search_matches_german_and_english_food_names(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executemany(
                """
                INSERT INTO bls_foods
                    (code, name, name_en, calories, protein, fat, carbs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("C131000", "Haferflocken", "Oat flakes", 348, 13.22, 6.65, 58.7),
                    ("C131001", "Hafer ganzes Korn", "Oat grain", 343, 11.3, 7.09, 55),
                ],
            )
            connection.commit()
        finally:
            connection.close()

        result = self.database.search_bls_foods("OAT")

        self.assertEqual([food["bls_code"] for food in result], ["C131001", "C131000"])
        self.assertEqual(result[1]["nutrition"]["calories"], 348)

    def test_german_wikibooks_recipe_parser_extracts_recipe_content(self) -> None:
        recipe = parse_wikibooks_recipe(
            "Kochbuch/ Schokokuchen",
            """== Zutaten für 4 Personen ==
* 150 gr. dunkle Schokolade
* 2 EL Butter
* Vanille-Extrakt
== Aufwand ==
Backzeit 30 Minuten
== Zubereitung ==
Schokolade schmelzen.
Teig verrühren und backen.""",
        )

        self.assertEqual(recipe["name"], "Schokokuchen")
        self.assertEqual(recipe["servings"], 4)
        self.assertEqual(
            recipe["ingredients"],
            [
                {"name": "dunkle Schokolade", "measure": "150 gr."},
                {"name": "Butter", "measure": "2 EL"},
                {"name": "Vanille-Extrakt", "measure": ""},
            ],
        )
        self.assertEqual(
            recipe["instructions"], "Schokolade schmelzen.\nTeig verrühren und backen."
        )
        self.assertEqual(
            recipe["source"], "Wikibooks Kochbuch"
        )
        self.assertIn("de.wikibooks.org/wiki/Kochbuch/_Schokokuchen", recipe["source_url"])

    def test_german_recipe_search_fetches_and_parses_wikibooks_pages(self) -> None:
        class Response:
            def __init__(self, payload: dict) -> None:
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            def raise_for_status(self) -> None:
                return None

            async def json(self) -> dict:
                return self.payload

        class Session:
            def __init__(self) -> None:
                self.params = []
                self.headers = []

            def get(self, url: str, *, params: dict, timeout, headers: dict):
                self.params.append(params)
                self.headers.append(headers)
                if params.get("list") == "search":
                    return Response(
                        {
                            "query": {
                                "search": [
                                    {
                                        "pageid": 342,
                                        "title": (
                                            "Kochbuch/ Passierte Kartoffelsuppe "
                                            "mit Lachsstreifen"
                                        ),
                                        "wordcount": 185,
                                    }
                                ]
                            }
                        }
                    )
                return Response(
                    {
                        "query": {
                            "pages": {
                                "342": {
                                    "revisions": [
                                        {
                                            "slots": {
                                                "main": {
                                                    "*": """== Zutaten ==
* 800 g Kartoffeln
== Zubereitung ==
Kartoffeln kochen."""
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                )

        session = Session()
        recipes = asyncio.run(search_recipes(session, "Kartoffelsuppe"))

        self.assertEqual(len(session.params), 2)
        self.assertEqual(len(session.headers), 2)
        self.assertEqual(
            session.headers[0]["User-Agent"],
            "WeeklyMealPlanner/1.7.3 "
            "(+https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner)",
        )
        self.assertEqual(session.headers[0], session.headers[1])
        self.assertEqual(
            session.params[0]["srsearch"], "Kartoffelsuppe"
        )
        self.assertEqual(recipes[0]["name"], "Passierte Kartoffelsuppe mit Lachsstreifen")
        self.assertEqual(
            recipes[0]["ingredients"],
            [{"name": "Kartoffeln", "measure": "800 g"}],
        )
        self.assertEqual(recipes[0]["instructions"], "Kartoffeln kochen.")


class MealPlannerLogicTests(unittest.TestCase):
    def test_dashboard_includes_per_portion_calories_for_each_recipe(self) -> None:
        dashboard = build_dashboard_data(
            {"2026-10-05": {"lunch": "Soup"}},
            [
                {
                    "name": "Soup",
                    "meal_type": "lunch",
                    "servings": 2,
                    "ingredients": {
                        "Beans": {
                            "amount": 200,
                            "unit": "g",
                            "nutrition_per_100g": {
                                "calories": 80,
                                "protein": 5,
                                "fat": 1,
                                "carbs": 12,
                            },
                        }
                    },
                }
            ],
            household_servings=2,
            target_kcal=2000,
            food_search={"query": "", "results": []},
            week_start=date(2026, 10, 5),
        )

        self.assertEqual(
            dashboard["week_days"],
            [f"2026-10-{day:02}" for day in range(5, 12)],
        )
        self.assertEqual(
            dashboard["meals"],
            [
                {
                    "name": "Soup",
                    "meal_type": "lunch",
                    "source_name": "",
                    "calories": 80,
                }
            ],
        )

    def test_daily_calorie_total_includes_all_meal_types(self) -> None:
        nutrition = {
            "calories": 100,
            "protein": 10,
            "fat": 5,
            "carbs": 10,
        }
        meals = [
            {
                "name": name,
                "meal_type": meal_type,
                "servings": 1,
                "ingredients": {
                    name: {
                        "amount": calories,
                        "unit": "g",
                        "nutrition_per_100g": nutrition,
                    }
                },
            }
            for name, meal_type, calories in (
                ("Porridge", "breakfast", 300),
                ("Soup", "lunch", 450),
                ("Pasta", "dinner", 650),
            )
        ]

        totals = calculate_week_nutrition(
            {
                "2026-10-05": {
                    "breakfast": "Porridge",
                    "lunch": "Soup",
                    "dinner": "Pasta",
                }
            },
            meals,
            target_kcal=2000,
        )

        self.assertEqual(totals["per_day"]["2026-10-05"], 1400)

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

    def test_piece_ingredients_use_entered_weight_for_nutrition(self) -> None:
        ingredients = {
            "Ei": {
                "amount": 2,
                "unit": "Stück",
                "weight_per_unit_g": 60,
                "nutrition_per_100g": {
                    "calories": 150,
                    "protein": 12,
                    "fat": 10,
                    "carbs": 1,
                },
            }
        }

        totals, missing = calculate_meal_nutrition(ingredients)

        self.assertEqual(totals["calories"], 180)
        self.assertEqual(missing, [])

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
