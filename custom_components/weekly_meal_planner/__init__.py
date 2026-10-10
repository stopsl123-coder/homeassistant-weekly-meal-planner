"""Home Assistant setup for Weekly Meal Planner."""

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
from datetime import date, timedelta
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .database import MealPlannerDatabase
from .mealplanner import (
    build_dashboard_data,
    generate_week_plan,
    monday_for,
)
from .nutrition_api import get_nutrition_for_item

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
SERVICE_NAMES = ("add_meal", "generate_week_plan", "generate_shopping_list")
MEAL_TYPES = {"breakfast", "lunch", "dinner"}
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {vol.Required("api_key"): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class MealPlannerCoordinator(DataUpdateCoordinator):
    """Provide persisted planner data to sensors and services."""

    def __init__(
        self,
        hass: HomeAssistant,
        database: MealPlannerDatabase,
    ) -> None:
        self.database = database
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        today = dt_util.now().date()
        start = monday_for(today)
        try:
            meals, plan = await self.hass.async_add_executor_job(
                self._load_dashboard_inputs, start.isoformat()
            )
        except (OSError, sqlite3.Error, ValueError, TypeError) as err:
            raise UpdateFailed(f"Planerdaten konnten nicht geladen werden: {err}") from err
        return build_dashboard_data(plan, meals)

    def _load_dashboard_inputs(
        self, week_start: str
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
        return self.database.get_meals(), self.database.get_week_plan(week_start)


def _validate_ingredients(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise vol.Invalid("Add at least one ingredient.")

    validated: dict[str, dict[str, Any]] = {}
    for name, details in value.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise vol.Invalid("Ingredient names must be 1-100 characters.")
        normalized_name = name.strip()
        if normalized_name in validated:
            raise vol.Invalid(f"Ingredient '{normalized_name}' was provided twice.")
        if not isinstance(details, dict):
            raise vol.Invalid(f"Ingredient '{name}' must be an object.")

        amount = details.get("amount")
        unit = details.get("unit")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount <= 0
        ):
            raise vol.Invalid(f"Ingredient '{name}' must have a positive amount.")
        if not isinstance(unit, str) or not unit.strip() or len(unit) > 30:
            raise vol.Invalid(f"Ingredient '{name}' must have a valid unit.")
        validated[normalized_name] = {"amount": float(amount), "unit": unit.strip()}
    return validated


ADD_MEAL_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
        vol.Required("meal_type"): vol.In(MEAL_TYPES),
        vol.Required("ingredients"): _validate_ingredients,
    }
)
EMPTY_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Import legacy YAML configuration into a config entry."""
    if domain_config := config.get(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=domain_config,
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    database = MealPlannerDatabase(hass.config.path("mealplanner.db"))
    try:
        await hass.async_add_executor_job(database.initialize)
    except (OSError, sqlite3.Error) as err:
        raise ConfigEntryNotReady(f"Could not initialize meal database: {err}") from err

    coordinator = MealPlannerCoordinator(hass, database)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "database": database,
        "coordinator": coordinator,
        "api_key": entry.data["api_key"],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    for service in SERVICE_NAMES:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    return True


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    database: MealPlannerDatabase = data["database"]
    coordinator: MealPlannerCoordinator = data["coordinator"]
    api_key: str = data["api_key"]
    session = async_get_clientsession(hass)

    async def handle_add_meal(call: ServiceCall) -> None:
        ingredients = call.data["ingredients"]
        names = list(ingredients)
        try:
            nutrition_values = await asyncio.gather(
                *(
                    get_nutrition_for_item(session, api_key, name)
                    for name in names
                )
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise HomeAssistantError(
                "USDA-Abfrage fehlgeschlagen. API-Schlüssel und Internetverbindung prüfen."
            ) from None

        enriched: dict[str, dict[str, Any]] = {}
        for name, details, nutrition in zip(
            names, ingredients.values(), nutrition_values, strict=True
        ):
            if nutrition is None:
                raise HomeAssistantError(
                    f"USDA lieferte keine Nährwerte für „{name}“. "
                    "Schreibweise prüfen; die Suche benötigt möglicherweise englische Namen."
                )
            enriched[name] = {
                **details,
                "nutrition_per_100g": nutrition,
            }

        await hass.async_add_executor_job(
            database.add_meal,
            call.data["name"],
            call.data["meal_type"],
            enriched,
        )
        await coordinator.async_request_refresh()

    async def handle_generate_week_plan(call: ServiceCall) -> None:
        meals = await hass.async_add_executor_job(database.get_meals)
        start = monday_for(dt_util.now().date())
        plan = generate_week_plan(meals, start)
        if not plan:
            raise HomeAssistantError(
                "Vor der Wochenplanung mindestens ein Mittag- oder Abendessen speichern."
            )
        await hass.async_add_executor_job(
            database.replace_week_plan, start.isoformat(), plan
        )
        await coordinator.async_request_refresh()

    async def handle_generate_shopping_list(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, "add_meal", handle_add_meal, schema=ADD_MEAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "generate_week_plan",
        handle_generate_week_plan,
        schema=EMPTY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "generate_shopping_list",
        handle_generate_shopping_list,
        schema=EMPTY_SCHEMA,
    )
