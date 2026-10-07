from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

class WeeklyMealPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Weekly Meal Planner."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            api_key = user_input.get("api_key")
            if not api_key:
                errors["base"] = "no_api_key"
            else:
                return self.async_create_entry(
                    title="Weekly Meal Planner",
                    data={"api_key": api_key},
                )

        data_schema = vol.Schema(
            {
                vol.Required("api_key"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
