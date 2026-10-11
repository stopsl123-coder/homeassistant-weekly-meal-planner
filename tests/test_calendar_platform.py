from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weekly_meal_planner import MealPlannerCoordinator
from custom_components.weekly_meal_planner.calendar import WeeklyMealPlanCalendar
from custom_components.weekly_meal_planner.const import DOMAIN
from custom_components.weekly_meal_planner.mealplanner import monday_for


@pytest.fixture(autouse=True)
def enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.mark.asyncio
async def test_weekly_plan_is_available_in_home_assistant_calendar(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "test-key"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: MealPlannerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    database = coordinator.database
    week_start = monday_for(dt_util.now().date())
    for name, meal_type, calories in (
        ("Gemüsesuppe", "lunch", 100),
        ("Linsencurry", "dinner", 200),
        ("Salat", "lunch", 50),
        ("Bohnensalat", "lunch", 75),
    ):
        await hass.async_add_executor_job(
            database.add_meal,
            name,
            meal_type,
            1,
            {
                name: {
                    "amount": 100,
                    "unit": "g",
                    "nutrition_per_100g": {
                        "calories": calories,
                        "protein": 2,
                        "fat": 1,
                        "carbs": 10,
                    },
                }
            },
        )
    plan = {
        week_start.isoformat(): {
            "lunch": "Gemüsesuppe",
            "dinner": "Linsencurry",
        }
    }
    await hass.async_add_executor_job(
        database.replace_week_plan, week_start.isoformat(), plan
    )
    await coordinator.async_refresh()

    calendar = WeeklyMealPlanCalendar(coordinator, entry.entry_id)
    start = dt_util.start_of_local_day(
        datetime.combine(week_start, time.min)
    )
    events = await calendar.async_get_events(
        hass, start, start + timedelta(days=7)
    )

    assert len(events) == 1
    assert events[0].start == week_start
    assert events[0].end == week_start + timedelta(days=1)
    assert coordinator.data["week_days"] == [
        (week_start + timedelta(days=offset)).isoformat() for offset in range(7)
    ]
    assert "Mittagessen: Gemüsesuppe" in events[0].summary
    assert "100 kcal pro Portion" in events[0].summary
    assert "Abendessen: Linsencurry" in events[0].summary
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": week_start.isoformat(),
            "meal_type": "lunch",
            "meal_name": "Salat",
        },
        blocking=True,
    )
    updated_plan = await hass.async_add_executor_job(
        database.get_week_plan, week_start.isoformat()
    )
    assert updated_plan[week_start.isoformat()]["lunch"] == "Salat"
    assert coordinator.data["nutrition"]["per_day"][week_start.isoformat()] == 250
    next_day = (week_start + timedelta(days=1)).isoformat()
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": next_day,
            "meal_type": "lunch",
            "meal_name": "Bohnensalat",
        },
        blocking=True,
    )
    updated_plan = await hass.async_add_executor_job(
        database.get_week_plan, week_start.isoformat()
    )
    assert updated_plan[week_start.isoformat()]["lunch"] == "Salat"
    assert updated_plan[next_day]["lunch"] == "Bohnensalat"
    await hass.async_add_executor_job(
        database.add_meal,
        "Haferbrei",
        "breakfast",
        1,
        {
            "Haferflocken": {
                "amount": 50,
                "unit": "g",
                "nutrition_per_100g": {
                    "calories": 350,
                    "protein": 10,
                    "fat": 7,
                    "carbs": 60,
                },
            }
        },
    )
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": week_start.isoformat(),
            "meal_type": "breakfast",
            "meal_name": "Haferbrei",
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "generate_week_plan",
        {},
        blocking=True,
    )
    updated_plan = await hass.async_add_executor_job(
        database.get_week_plan, week_start.isoformat()
    )
    assert updated_plan[week_start.isoformat()]["breakfast"] == "Haferbrei"
    events = await calendar.async_get_events(
        hass, start, start + timedelta(days=7)
    )
    assert "Frühstück: Haferbrei" in events[0].summary
    assert hass.states.get("calendar.weekly_meal_planner") is not None
    assert hass.services.has_service(DOMAIN, "search_ingredient")
    assert hass.services.has_service(DOMAIN, "set_planned_meal")

    next_week = week_start + timedelta(days=7)
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": next_week.isoformat(),
            "meal_type": "lunch",
            "meal_name": "Salat",
        },
        blocking=True,
    )
    next_week_data = await hass.services.async_call(
        DOMAIN,
        "get_week_data",
        {"week_start": next_week.isoformat()},
        blocking=True,
        return_response=True,
    )
    assert next_week_data["week_start"] == next_week.isoformat()
    assert next_week_data["plan"][next_week.isoformat()]["lunch"] == "Salat"
    assert next_week_data["shopping_list"]["Salat"] == {
        "amount": 200.0,
        "unit": "g",
    }
    assert coordinator.data["week_start"] == week_start.isoformat()
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": next_week.isoformat(),
            "meal_type": "breakfast",
            "meal_name": "Haferbrei",
        },
        blocking=True,
    )

    await hass.services.async_call(
        DOMAIN,
        "generate_week_plan",
        {"week_start": next_week.isoformat()},
        blocking=True,
    )
    next_week_data = await hass.services.async_call(
        DOMAIN,
        "get_week_data",
        {"week_start": next_week.isoformat()},
        blocking=True,
        return_response=True,
    )
    assert next_week_data["plan"][next_week.isoformat()]["breakfast"] == "Haferbrei"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_ingredient_search_returns_results_to_service_caller(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "test-key"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    database = hass.data[DOMAIN][entry.entry_id]["database"]
    matches = [
        {
            "fdc_id": 123,
            "description": "Egg, whole, raw",
            "nutrition": {
                "calories": 143,
                "protein": 12.56,
                "fat": 9.51,
                "carbs": 0.72,
            },
        }
    ]
    await hass.async_add_executor_job(
        database.cache_nutrition_search, "egg", matches
    )
    coordinator: MealPlannerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    response = await hass.services.async_call(
        DOMAIN,
        "search_ingredient",
        {"query": "egg", "source": "usda"},
        blocking=True,
        return_response=True,
    )

    assert response == {"query": "egg", "source": "usda", "results": matches}
    await hass.services.async_call(
        DOMAIN,
        "add_meal",
        {
            "name": "Rührei",
            "meal_type": "breakfast",
            "servings": 1,
            "ingredients": {
                "Ei": {
                    "amount": 2,
                    "unit": "Stück",
                    "fdc_id": 123,
                    "weight_per_unit_g": 60,
                }
            },
        },
        blocking=True,
    )
    stored_meal = await hass.async_add_executor_job(database.get_meal, "Rührei")
    assert stored_meal["ingredients"]["Ei"]["weight_per_unit_g"] == 60
    assert stored_meal["ingredients"]["Ei"]["nutrition_source"] == "usda"
    assert stored_meal["ingredients"]["Ei"]["nutrition_id"] == 123
    assert any(meal["name"] == "Rührei" for meal in coordinator.data["meals"])

    today = dt_util.now().date()
    week_start = monday_for(today)
    await hass.services.async_call(
        DOMAIN,
        "set_planned_meal",
        {
            "day": today.isoformat(),
            "meal_type": "breakfast",
            "meal_name": "Rührei",
        },
        blocking=True,
    )
    plan = await hass.async_add_executor_job(
        database.get_week_plan, week_start.isoformat()
    )
    assert plan[today.isoformat()]["breakfast"] == "Rührei"

    await hass.services.async_call(
        DOMAIN,
        "delete_meal",
        {"name": "Rührei"},
        blocking=True,
    )
    assert await hass.async_add_executor_job(database.get_meal, "Rührei") is None
    plan_after_delete = await hass.async_add_executor_job(
        database.get_week_plan, week_start.isoformat()
    )
    assert "breakfast" not in plan_after_delete.get(today.isoformat(), {})
    assert all(meal["name"] != "Rührei" for meal in coordinator.data["meals"])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_bls_search_uses_local_database(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": ""})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    database = hass.data[DOMAIN][entry.entry_id]["database"]
    await hass.async_add_executor_job(database.initialize)
    with database._connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO bls_foods
                (code, name, name_en, calories, protein, fat, carbs)
            VALUES ('C131000', 'Haferflocken', 'Oat flakes', 348, 13.22, 6.65, 58.7)
            """
        )
    response = await hass.services.async_call(
        DOMAIN,
        "search_ingredient",
        {"query": "hafer"},
        blocking=True,
        return_response=True,
    )

    assert response["source"] == "bls"
    assert response["results"][0]["bls_code"] == "C131000"
    assert response["results"][0]["nutrition"]["calories"] == 348
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_recipe_search_returns_importable_results(hass, monkeypatch) -> None:
    import custom_components.weekly_meal_planner as integration_module

    async def mock_search_recipes(session, query):
        assert query == "Kartoffelsuppe"
        return [
            {
                "id": "Kochbuch/ Kartoffelsuppe",
                "name": "Kartoffelsuppe",
                "servings": 4,
                "instructions": "Kartoffeln garen.",
                "source_url": "https://de.wikibooks.org/wiki/Kochbuch/_Kartoffelsuppe",
                "ingredients": [{"name": "Kartoffeln", "measure": "500 g"}],
                "source": "Wikibooks Kochbuch",
            }
        ]

    monkeypatch.setattr(integration_module, "search_recipes", mock_search_recipes)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": ""})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN,
        "search_recipe",
        {"query": "Kartoffelsuppe"},
        blocking=True,
        return_response=True,
    )

    assert response["results"][0]["name"] == "Kartoffelsuppe"
    assert response["results"][0]["ingredients"][0]["measure"] == "500 g"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_add_meal_saves_bls_nutrition_and_recipe_details(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": ""})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    database = hass.data[DOMAIN][entry.entry_id]["database"]
    with database._connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO bls_foods
                (code, name, name_en, calories, protein, fat, carbs)
            VALUES ('C131000', 'Haferflocken', 'Oat flakes', 348, 13.22, 6.65, 58.7)
            """
        )

    await hass.services.async_call(
        DOMAIN,
        "add_meal",
        {
            "name": "Haferbrei",
            "meal_type": "breakfast",
            "servings": 2,
            "ingredients": {
                "Haferflocken": {
                    "amount": 100,
                    "unit": "g",
                    "bls_code": "C131000",
                }
            },
            "instructions": "Mit Milch aufkochen.",
            "source_url": "https://example.org/haferbrei",
            "source_name": "Wikibooks Kochbuch",
        },
        blocking=True,
    )

    meal = await hass.async_add_executor_job(database.get_meal, "Haferbrei")
    ingredient = meal["ingredients"]["Haferflocken"]
    assert ingredient["nutrition_per_100g"]["calories"] == 348
    assert ingredient["nutrition_source"] == "bls"
    details = await hass.services.async_call(
        DOMAIN,
        "get_meal_details",
        {"name": "Haferbrei"},
        blocking=True,
        return_response=True,
    )
    assert details["meal_type"] == "breakfast"
    assert details["servings"] == 2
    assert details["ingredients"]["Haferflocken"]["amount"] == 100
    assert details["ingredients"]["Haferflocken"]["unit"] == "g"
    assert details["instructions"] == "Mit Milch aufkochen."
    assert details["source_name"] == "Wikibooks Kochbuch"
    assert details["source_url"] == "https://example.org/haferbrei"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_shopping_item_can_be_checked_and_unchecked(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": ""})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator: MealPlannerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    database = coordinator.database
    week_start = monday_for(dt_util.now().date()).isoformat()
    await hass.async_add_executor_job(
        database.add_meal,
        "Bohnensalat",
        "lunch",
        1,
        {"Bohnen": {"amount": 200, "unit": "g"}},
    )
    await hass.async_add_executor_job(
        database.replace_week_plan,
        week_start,
        {week_start: {"lunch": "Bohnensalat"}},
    )

    response = await hass.services.async_call(
        DOMAIN,
        "set_shopping_item",
        {"week_start": week_start, "item_name": "Bohnen", "checked": True},
        blocking=True,
        return_response=True,
    )
    assert response["shopping_checked"] == {"Bohnen": True}

    response = await hass.services.async_call(
        DOMAIN,
        "set_shopping_item",
        {"week_start": week_start, "item_name": "Bohnen", "checked": False},
        blocking=True,
        return_response=True,
    )
    assert response["shopping_checked"] == {}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
