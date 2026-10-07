import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .nutrition_api import set_api_key
from .mealplanner import add_meal, generate_week_plan
from .smart_planner import generate_shopping_list

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config):
    # YAML-basierte Konfiguration (Fallback)
    domain_config = config.get(DOMAIN, {})
    api_key = domain_config.get("api_key")
    if api_key:
        set_api_key(api_key)
        _LOGGER.info("Weekly Meal Planner API-Key aus YAML geladen.")

    # Services registrieren
    register_services(hass)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api_key = entry.data.get("api_key")
    if api_key:
        set_api_key(api_key)
        _LOGGER.info("Weekly Meal Planner API-Key aus Config-Flow geladen.")
    else:
        _LOGGER.warning("Weekly Meal Planner: Kein API-Key gesetzt.")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entry_id"] = entry.entry_id

    # Services registrieren
    register_services(hass)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.get(DOMAIN, {}).pop("entry_id", None)
    return True

def register_services(hass: HomeAssistant):
    """Registriert alle Weekly Meal Planner Services."""

    async def handle_add_meal(call: ServiceCall):
        meal = call.data.get("meal")
        day = call.data.get("day")
        add_meal(meal, day)

    async def handle_generate_week_plan(call: ServiceCall):
        generate_week_plan()

    async def handle_generate_shopping_list(call: ServiceCall):
        generate_shopping_list()

    hass.services.async_register(DOMAIN, "add_meal", handle_add_meal)
    hass.services.async_register(DOMAIN, "generate_week_plan", handle_generate_week_plan)
    hass.services.async_register(DOMAIN, "generate_shopping_list", handle_generate_shopping_list)

    _LOGGER.info("Weekly Meal Planner Services erfolgreich registriert.")
