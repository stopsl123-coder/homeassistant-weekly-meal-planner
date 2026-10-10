"""Sensors for the current meal plan."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MealPlannerCoordinator
from .const import DOMAIN

SHOPPING_LIST_DESCRIPTION = SensorEntityDescription(
    key="shopping_list",
    name="Weekly Meal Planner Shopping List",
    icon="mdi:cart-outline",
    native_unit_of_measurement="items",
    state_class=SensorStateClass.MEASUREMENT,
)
CALORIES_DESCRIPTION = SensorEntityDescription(
    key="weekly_calories",
    name="Weekly Meal Planner Calories",
    icon="mdi:fire",
    native_unit_of_measurement="kcal",
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MealPlannerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities(
        [
            ShoppingListSensor(coordinator, entry.entry_id),
            MealCaloriesSensor(coordinator, entry.entry_id),
        ]
    )


class ShoppingListSensor(CoordinatorEntity, SensorEntity):
    entity_description = SHOPPING_LIST_DESCRIPTION

    def __init__(
        self, coordinator: MealPlannerCoordinator, entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_shopping_list"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data["shopping_list"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "items": self.coordinator.data["shopping_list"],
            "latest_nutrition_search": self.coordinator.data["food_search"],
        }


class MealCaloriesSensor(CoordinatorEntity, SensorEntity):
    entity_description = CALORIES_DESCRIPTION

    def __init__(
        self, coordinator: MealPlannerCoordinator, entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_weekly_calories"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data["nutrition"]["week_total"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nutrition = self.coordinator.data["nutrition"]
        return {
            "per_day": nutrition["per_day"],
            "daily_macros": nutrition["daily_macros"],
            "week_macros": nutrition["week_macros"],
            "week_target": nutrition["week_target"],
            "difference": nutrition["difference"],
            "missing_nutrition": nutrition["missing_nutrition"],
            "plan": self.coordinator.data["plan"],
            "week_days": self.coordinator.data["week_days"],
            "meals": self.coordinator.data["meals"],
        }
