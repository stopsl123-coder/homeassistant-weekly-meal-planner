import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .nutrition_api import set_api_key

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config):
    # YAML-basierte Konfiguration (Fallback)
    domain_config = config.get(DOMAIN, {})
    api_key = domain_config.get("api_key")
    if api_key:
        set_api_key(api_key)
        _LOGGER.info("Weekly Meal Planner API-Key aus YAML geladen.")
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
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.get(DOMAIN, {}).pop("entry_id", None)
    return True
