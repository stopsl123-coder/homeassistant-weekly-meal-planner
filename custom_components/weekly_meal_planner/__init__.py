"""Home Assistant setup for Weekly Meal Planner."""

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlsplit

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
from .bls import BLS_DATA_URL
from .mealplanner import (
    build_dashboard_data,
    generate_week_plan,
    monday_for,
)
from .nutrition_api import search_nutrition_for_item
from .recipe_api import search_recipes

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]
SERVICE_NAMES = (
    "add_meal",
    "delete_meal",
    "generate_week_plan",
    "generate_shopping_list",
    "get_week_data",
    "search_ingredient",
    "search_recipe",
    "get_meal_details",
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
        return await self.async_get_week_data(monday_for(dt_util.now().date()))

    async def async_get_week_data(self, start: date) -> dict[str, Any]:
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
        bls_code = details.get("bls_code")
        if fdc_id is not None and bls_code is not None:
            raise vol.Invalid(
                f"Ingredient '{name}' cannot have both USDA and BLS food IDs."
            )
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
        if bls_code is not None and (
            not isinstance(bls_code, str) or not bls_code.strip() or len(bls_code) > 20
        ):
            raise vol.Invalid(f"Ingredient '{name}' has an invalid BLS food code.")
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
            **({"bls_code": bls_code.strip()} if bls_code is not None else {}),
            **(
                {"weight_per_unit_g": float(weight_per_unit_g)}
                if weight_per_unit_g is not None
                else {}
            ),
        }
    return validated


def _validate_https_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise vol.Invalid("Recipe source URL must use HTTPS.")
    return url


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
        vol.Optional("instructions", default=""): vol.All(str, vol.Length(max=20_000)),
        vol.Optional("source_url", default=""): vol.All(
            str, vol.Length(max=2_000), _validate_https_url
        ),
        vol.Optional("source_name", default=""): vol.All(str, vol.Length(max=100)),
    }
)
DELETE_MEAL_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
    }
)
MEAL_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Required("name"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
    }
)
EMPTY_SCHEMA = vol.Schema({})
SEARCH_INGREDIENT_SCHEMA = vol.Schema(
    {
        vol.Required("query"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
        vol.Optional("source", default="bls"): vol.In({"bls", "usda"}),
        vol.Optional("force_refresh", default=False): cv.boolean,
    }
)
SEARCH_RECIPE_SCHEMA = vol.Schema(
    {
        vol.Required("query"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
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
WEEK_START_SCHEMA = vol.Schema(
    {
        vol.Optional("week_start"): vol.All(
            str, str.strip, vol.Length(min=10, max=10)
        )
    }
)


def _validate_week_start(value: str | None) -> date:
    current_week = monday_for(dt_util.now().date())
    if value is None:
        return current_week
    try:
        week_start = date.fromisoformat(value)
    except ValueError as err:
        raise HomeAssistantError("Ungültiges Startdatum der Woche.") from err
    if week_start.isoformat() != value or week_start.weekday() != 0:
        raise HomeAssistantError(
            "Der Wochenstart muss ein Montag im Format YYYY-MM-DD sein."
        )
    if week_start not in (current_week, current_week + timedelta(days=7)):
        raise HomeAssistantError(
            "Du kannst die aktuelle oder die nächste Woche auswählen."
        )
    return week_start


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
        "api_key": entry.options.get("api_key", entry.data.get("api_key", "")),
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
    bls_import_lock = asyncio.Lock()

    async def ensure_bls_loaded() -> None:
        if await hass.async_add_executor_job(database.has_bls_data):
            return
        async with bls_import_lock:
            if await hass.async_add_executor_job(database.has_bls_data):
                return
            try:
                async with session.get(
                    BLS_DATA_URL,
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as response:
                    response.raise_for_status()
                    if (
                        response.content_length is not None
                        and response.content_length > 60_000_000
                    ):
                        raise HomeAssistantError(
                            "BLS-Download überschreitet die erlaubte Dateigröße."
                        )
                    payload = await response.read()
                if len(payload) > 60_000_000:
                    raise HomeAssistantError(
                        "BLS-Download überschreitet die erlaubte Dateigröße."
                    )
                imported = await hass.async_add_executor_job(
                    database.import_bls_archive, payload
                )
            except HomeAssistantError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, sqlite3.Error) as err:
                _LOGGER.warning("BLS-Daten konnten nicht geladen werden: %s", err)
                raise HomeAssistantError(
                    "BLS-Daten konnten nicht geladen werden. Internetverbindung prüfen."
                ) from err
            _LOGGER.info("BLS 4.0 geladen: %s Lebensmittel", imported)

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
        if call.data["source"] == "bls":
            await ensure_bls_loaded()
            results = await hass.async_add_executor_job(
                database.search_bls_foods, query
            )
            return {"query": query, "source": "bls", "results": results}
        if not api_key:
            raise HomeAssistantError(
                "Für USDA-Suche API-Schlüssel in Integration-Optionen eintragen."
            )
        results = await search_and_cache(query, call.data["force_refresh"])
        if not results:
            raise HomeAssistantError(
                f"USDA fand keine verwendbaren Nährwerte für „{query}“."
            )
        await coordinator.async_request_refresh()
        return {"query": query, "source": "usda", "results": results}

    async def handle_search_recipe(call: ServiceCall) -> dict[str, Any]:
        query = call.data["query"]
        try:
            results = await search_recipes(session, query)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.warning("Rezeptsuche fehlgeschlagen: %s", err)
            raise HomeAssistantError(
                "Wikibooks-Rezeptsuche fehlgeschlagen. Internetverbindung prüfen."
            ) from err
        return {"query": query, "results": results}

    async def handle_get_meal_details(call: ServiceCall) -> dict[str, Any]:
        meal = await hass.async_add_executor_job(
            database.get_meal, call.data["name"]
        )
        if meal is None:
            raise HomeAssistantError(
                f"Gericht „{call.data['name']}“ wurde nicht gefunden."
            )
        return {
            "name": meal["name"],
            "meal_type": meal["meal_type"],
            "servings": meal["servings"],
            "ingredients": meal["ingredients"],
            "instructions": meal["instructions"],
            "source_url": meal["source_url"],
            "source_name": meal["source_name"],
        }

    async def handle_add_meal(call: ServiceCall) -> None:
        ingredients = call.data["ingredients"]
        names = list(ingredients)
        nutrition_values = []
        nutrition_ids: list[tuple[str, str | int]] = []
        for name, details in ingredients.items():
            bls_code = details.get("bls_code")
            if bls_code is not None:
                food = await hass.async_add_executor_job(
                    database.get_bls_food, bls_code
                )
                if food is None:
                    raise HomeAssistantError(
                        f"BLS-Auswahl für „{name}“ wurde nicht gefunden. Zutat erneut suchen."
                    )
                nutrition_values.append(food["nutrition"])
                nutrition_ids.append(("bls", bls_code))
                continue
            fdc_id = details.get("fdc_id")
            if fdc_id is None:
                if not api_key:
                    raise HomeAssistantError(
                        "Bitte für jede Zutat einen BLS-Treffer auswählen."
                    )
                matches = await search_and_cache(name)
                if not matches:
                    raise HomeAssistantError(
                        f"USDA fand keine verwendbaren Nährwerte für „{name}“."
                    )
                selected = matches[0]
                nutrition_values.append(selected["nutrition"])
                details["fdc_id"] = selected["fdc_id"]
                nutrition_ids.append(("usda", selected["fdc_id"]))
                continue
            cached = await hass.async_add_executor_job(
                database.get_cached_nutrition, fdc_id
            )
            if cached is None:
                raise HomeAssistantError(
                    f"USDA-Auswahl für „{name}“ ist abgelaufen. Zutat erneut suchen."
                )
            nutrition_values.append(cached["nutrition"])
            nutrition_ids.append(("usda", fdc_id))

        enriched: dict[str, dict[str, Any]] = {}
        for name, details, nutrition, (source, identifier) in zip(
            names, ingredients.values(), nutrition_values, nutrition_ids, strict=True
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
                "nutrition_source": source,
                "nutrition_id": identifier,
            }

        await hass.async_add_executor_job(
            database.add_meal,
            call.data["name"],
            call.data["meal_type"],
            call.data["servings"],
            enriched,
            call.data["instructions"],
            call.data["source_url"],
            call.data["source_name"],
        )
        await coordinator.async_refresh()

    async def handle_delete_meal(call: ServiceCall) -> None:
        deleted = await hass.async_add_executor_job(
            database.delete_meal, call.data["name"]
        )
        if not deleted:
            raise HomeAssistantError(
                f"Gericht „{call.data['name']}“ wurde nicht gefunden."
            )
        await coordinator.async_refresh()

    async def handle_generate_week_plan(call: ServiceCall) -> None:
        start = _validate_week_start(call.data.get("week_start"))
        meals = await hass.async_add_executor_job(database.get_meals)
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
        if start == monday_for(dt_util.now().date()):
            await coordinator.async_refresh()

    async def handle_generate_shopping_list(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    async def handle_get_week_data(call: ServiceCall) -> dict[str, Any]:
        week_start = _validate_week_start(call.data.get("week_start"))
        return await coordinator.async_get_week_data(week_start)

    async def handle_set_planned_meal(call: ServiceCall) -> None:
        try:
            day = date.fromisoformat(call.data["day"])
        except ValueError as err:
            raise HomeAssistantError("Ungültiges Datum für den Wochenplan.") from err
        if day.isoformat() != call.data["day"]:
            raise HomeAssistantError("Datum muss das Format YYYY-MM-DD haben.")

        current_week = monday_for(dt_util.now().date())
        if monday_for(day) not in (
            current_week,
            current_week + timedelta(days=7),
        ):
            raise HomeAssistantError(
                "Du kannst Gerichte nur für die aktuelle oder nächste Woche ändern."
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
        if monday_for(day) == current_week:
            await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN, "add_meal", handle_add_meal, schema=ADD_MEAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "delete_meal", handle_delete_meal, schema=DELETE_MEAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "generate_week_plan",
        handle_generate_week_plan,
        schema=WEEK_START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "get_week_data",
        handle_get_week_data,
        schema=WEEK_START_SCHEMA,
        supports_response=SupportsResponse.ONLY,
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
    hass.services.async_register(
        DOMAIN,
        "search_recipe",
        handle_search_recipe,
        schema=SEARCH_RECIPE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_meal_details",
        handle_get_meal_details,
        schema=MEAL_DETAILS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
