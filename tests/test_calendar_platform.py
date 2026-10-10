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
    plan = {
        week_start.isoformat(): {
            "lunch": "Gemüsesuppe",
            "dinner": "Linsencurry",
        }
    }
    await hass.async_add_executor_job(
        database.replace_week_plan, week_start.isoformat(), plan
    )
    await coordinator.async_request_refresh()

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
    assert "Mittagessen: Gemüsesuppe" in events[0].summary
    assert "Abendessen: Linsencurry" in events[0].summary
    assert hass.states.get("calendar.weekly_meal_planner") is not None
    assert hass.services.has_service(DOMAIN, "search_ingredient")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
