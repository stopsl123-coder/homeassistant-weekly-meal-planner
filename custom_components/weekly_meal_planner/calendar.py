"""Read-only calendar for the current weekly meal plan."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import MealPlannerCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MealPlannerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([WeeklyMealPlanCalendar(coordinator, entry.entry_id)])


class WeeklyMealPlanCalendar(CoordinatorEntity, CalendarEntity):
    """Expose each planned day as an all-day calendar event."""

    _attr_icon = "mdi:calendar-week"

    def __init__(
        self, coordinator: MealPlannerCoordinator, entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_meal_plan"
        self._attr_name = "Weekly Meal Planner"

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next(
            (
                event
                for event in self._events()
                if event.end_datetime_local > now
            ),
            None,
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return [
            event
            for event in self._events()
            if (
                event.end_datetime_local > start_date
                and event.start_datetime_local < end_date
            )
        ]

    def _events(self) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        meal_calories = {
            meal["name"]: meal["calories"]
            for meal in self.coordinator.data["meals"]
        }
        for day, meals in sorted(self.coordinator.data["plan"].items()):
            event_day = date.fromisoformat(day)
            if not meals:
                continue
            summary = "Essensplan: " + " · ".join(
                (
                    f"{self._meal_type_name(meal_type)}: {meal_name} "
                    f"({round(meal_calories[meal_name])} kcal pro Portion)"
                    if meal_calories.get(meal_name) is not None
                    else f"{self._meal_type_name(meal_type)}: {meal_name} "
                    "(Kalorien unbekannt)"
                )
                for meal_type, meal_name in meals.items()
            )
            nutrition = self.coordinator.data["nutrition"]["per_day"].get(day)
            description = (
                f"Tageskalorien: {nutrition} kcal"
                if nutrition is not None
                else "Nährwerte unvollständig oder nicht verfügbar."
            )
            events.append(
                CalendarEvent(
                    start=event_day,
                    end=event_day + timedelta(days=1),
                    summary=summary,
                    description=description,
                )
            )
        return events

    @staticmethod
    def _meal_type_name(meal_type: str) -> str:
        return {
            "breakfast": "Frühstück",
            "lunch": "Mittagessen",
            "dinner": "Abendessen",
        }.get(meal_type, meal_type)
