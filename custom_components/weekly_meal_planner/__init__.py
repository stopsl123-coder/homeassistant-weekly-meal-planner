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
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .database import MealPlannerDatabase
from .mealplanner import (
    build_dashboard_data,
    generate_week_plan,
    monday_for,
)
from .nutrition_api import search_nutrition_for_item

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]
SERVICE_NAMES = (
    "add_meal",
    "generate_week_plan",
    "generate_shopping_list",
    "search_ingredient",
    "set_planned_meal",
)
MEAL_TYPES = {"breakfast", "lunch", "dinner"}
CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({vol.Required("api_key"): cv.string})},
    extra=vol.ALLOW_EXTRA,
)
DEFAULT_SETTINGS = {
    "target_kcal": 2000,
    "household_servings": 2,
    "excluded_ingredients": "",
}


class MealPlannerCoordinator(DataUpdateCoordinator):
    """Provide persisted planner data to sensors and services."""

    def __init__(
        self,
        hass: HomeAssistant,
        database: MealPlannerDatabase,
    ) -> None:
        self.database = database
        self.settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
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
            meals, plan, recent_usage, food_search = await self.hass.async_add_executor_job(
                self._load_dashboard_inputs, start.isoformat()
            )
        except (OSError, sqlite3.Error, ValueError, TypeError) as err:
            raise UpdateFailed(f"Planerdaten konnten nicht geladen werden: {err}") from err
        return build_dashboard_data(
            plan,
            meals,
            self.settings["household_servings"],
            self.settings["target_kcal"],
            food_search,
            start,
        )

    def _load_dashboard_inputs(
        self, week_start: str
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, dict[str, str]],
        dict[str, int],
        dict[str, Any],
    ]:
        return (
            self.database.get_meals(),
            self.database.get_week_plan(week_start),
            self.database.get_recent_meal_usage(week_start),
            self.database.get_latest_nutrition_search(),
        )


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
        fdc_id = details.get("fdc_id")
        weight_per_unit_g = details.get("weight_per_unit_g")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount <= 0
        ):
            raise vol.Invalid(f"Ingredient '{name}' must have a positive amount.")
        if not isinstance(unit, str) or not unit.strip() or len(unit) > 30:
            raise vol.Invalid(f"Ingredient '{name}' must have a valid unit.")
        if fdc_id is not None and (
            isinstance(fdc_id, bool) or not isinstance(fdc_id, int) or fdc_id <= 0
        ):
            raise vol.Invalid(f"Ingredient '{name}' has an invalid USDA food ID.")
        if weight_per_unit_g is not None and (
            isinstance(weight_per_unit_g, bool)
            or not isinstance(weight_per_unit_g, (int, float))
            or not math.isfinite(weight_per_unit_g)
            or weight_per_unit_g <= 0
        ):
            raise vol.Invalid(
                f"Ingredient '{name}' must have a positive weight per unit in grams."
            )
        validated[normalized_name] = {
            "amount": float(amount),
            "unit": unit.strip(),
            **({"fdc_id": fdc_id} if fdc_id is not None else {}),
            **(
                {"weight_per_unit_g": float(weight_per_unit_g)}
                if weight_per_unit_g is not None
                else {}
            ),
        }
    return validated


def _coordinator_settings(entry: ConfigEntry) -> dict[str, Any]:
    settings = {**DEFAULT_SETTINGS, **entry.options}
    settings["excluded_ingredients"] = str(settings["excluded_ingredients"])
    settings["target_kcal"] = int(settings["target_kcal"])
    settings["household_servings"] = int(settings["household_servings"])
    return settings


ADD_MEAL_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
        vol.Required("meal_type"): vol.In(MEAL_TYPES),
        vol.Optional("servings", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Required("ingredients"): _validate_ingredients,
    }
)
EMPTY_SCHEMA = vol.Schema({})
SEARCH_INGREDIENT_SCHEMA = vol.Schema(
    {
        vol.Required("query"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
        vol.Optional("force_refresh", default=False): cv.boolean,
    }
)
SET_PLANNED_MEAL_SCHEMA = vol.Schema(
    {
        vol.Required("day"): vol.All(
            str, vol.Length(min=10, max=10)
        ),
        vol.Required("meal_type"): vol.In(MEAL_TYPES),
        vol.Required("meal_name"): vol.All(
            str, str.strip, vol.Length(min=1, max=100)
        ),
    }
)


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
    coordinator.settings = _coordinator_settings(entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "database": database,
        "coordinator": coordinator,
        "api_key": entry.options.get("api_key", entry.data["api_key"]),
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    database: MealPlannerDatabase = data["database"]
    coordinator: MealPlannerCoordinator = data["coordinator"]
    api_key: str = data["api_key"]
    session = async_get_clientsession(hass)

    async def search_and_cache(
        query: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        cached = None
        if not force_refresh:
            cached = await hass.async_add_executor_job(
                database.get_nutrition_search, query
            )
        if cached is not None:
            return cached
        try:
            results = await search_nutrition_for_item(session, api_key, query)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise HomeAssistantError(
                "USDA-Suche fehlgeschlagen. API-Schlüssel und Verbindung prüfen."
            ) from None
        if results:
            await hass.async_add_executor_job(
                database.cache_nutrition_search, query, results
            )
        return results

    async def handle_search_ingredient(call: ServiceCall) -> dict[str, Any]:
        query = call.data["query"]
        results = await search_and_cache(query, call.data["force_refresh"])
        if not results:
            raise HomeAssistantError(
                f"USDA fand keine verwendbaren Nährwerte für „{query}“."
            )
        await coordinator.async_request_refresh()
        return {"query": query, "results": results}

    async def handle_add_meal(call: ServiceCall) -> None:
        ingredients = call.data["ingredients"]
        names = list(ingredients)
        nutrition_values = []
        for name, details in ingredients.items():
            fdc_id = details.get("fdc_id")
            if fdc_id is None:
                matches = await search_and_cache(name)
                if not matches:
                    raise HomeAssistantError(
                        f"USDA fand keine verwendbaren Nährwerte für „{name}“."
                    )
                selected = matches[0]
                nutrition_values.append(selected["nutrition"])
                details["fdc_id"] = selected["fdc_id"]
                continue
            cached = await hass.async_add_executor_job(
                database.get_cached_nutrition, fdc_id
            )
            if cached is None:
                raise HomeAssistantError(
                    f"USDA-Auswahl für „{name}“ ist abgelaufen. Zutat erneut suchen."
                )
            nutrition_values.append(cached["nutrition"])

        enriched: dict[str, dict[str, Any]] = {}
        for name, details, nutrition in zip(
            names, ingredients.values(), nutrition_values, strict=True
        ):
            enriched[name] = {
                "amount": details["amount"],
                "unit": details["unit"],
                **(
                    {"weight_per_unit_g": details["weight_per_unit_g"]}
                    if "weight_per_unit_g" in details
                    else {}
                ),
                "nutrition_per_100g": nutrition,
                "usda_fdc_id": details["fdc_id"],
            }

        await hass.async_add_executor_job(
            database.add_meal,
            call.data["name"],
            call.data["meal_type"],
            call.data["servings"],
            enriched,
        )
        await coordinator.async_refresh()

    async def handle_generate_week_plan(call: ServiceCall) -> None:
        meals = await hass.async_add_executor_job(database.get_meals)
        start = monday_for(dt_util.now().date())
        recent_usage = await hass.async_add_executor_job(
            database.get_recent_meal_usage, start.isoformat()
        )
        excluded = {
            name.strip().casefold()
            for name in coordinator.settings["excluded_ingredients"].split(",")
            if name.strip()
        }
        plan = generate_week_plan(
            meals,
            start,
            coordinator.settings["target_kcal"],
            excluded,
            recent_usage,
        )
        if not plan:
            raise HomeAssistantError(
                "Vor der Wochenplanung mindestens ein Mittag- oder Abendessen speichern."
            )
        existing_plan = await hass.async_add_executor_job(
            database.get_week_plan, start.isoformat()
        )
        for day, day_meals in existing_plan.items():
            if "breakfast" in day_meals:
                plan.setdefault(day, {})["breakfast"] = day_meals["breakfast"]
        await hass.async_add_executor_job(
            database.replace_week_plan, start.isoformat(), plan
        )
        await coordinator.async_request_refresh()

    async def handle_generate_shopping_list(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    async def handle_set_planned_meal(call: ServiceCall) -> None:
        try:
            day = date.fromisoformat(call.data["day"])
        except ValueError as err:
            raise HomeAssistantError("Ungültiges Datum für den Wochenplan.") from err
        if day.isoformat() != call.data["day"]:
            raise HomeAssistantError("Datum muss das Format YYYY-MM-DD haben.")

        week_start = monday_for(dt_util.now().date())
        if monday_for(day) != week_start:
            raise HomeAssistantError(
                "Du kannst nur Gerichte der aktuellen Woche ändern."
            )

        meal = await hass.async_add_executor_job(
            database.get_meal, call.data["meal_name"]
        )
        if meal is None:
            raise HomeAssistantError(
                f"Gericht „{call.data['meal_name']}“ wurde nicht gefunden."
            )
        if meal["meal_type"] != call.data["meal_type"]:
            raise HomeAssistantError(
                "Gericht passt nicht zur ausgewählten Mahlzeit."
            )

        updated = await hass.async_add_executor_job(
            database.set_planned_meal,
            day.isoformat(),
            call.data["meal_type"],
            meal["name"],
        )
        if not updated:
            raise HomeAssistantError("Gericht konnte nicht in den Plan übernommen werden.")
        await coordinator.async_refresh()

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
    hass.services.async_register(
        DOMAIN,
        "set_planned_meal",
        handle_set_planned_meal,
        schema=SET_PLANNED_MEAL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "search_ingredient",
        handle_search_ingredient,
        schema=SEARCH_INGREDIENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
