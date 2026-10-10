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
        {"query": "egg"},
        blocking=True,
        return_response=True,
    )

    assert response == {"query": "egg", "results": matches}
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
    assert stored_meal["ingredients"]["Ei"]["usda_fdc_id"] == 123
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

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
