from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class WeeklyMealPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Weekly Meal Planner."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            api_key = user_input["api_key"].strip()
            if api_key:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Weekly Meal Planner", data={"api_key": api_key}
                )

        data_schema = vol.Schema(
            {
                vol.Required("api_key"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors={"base": "no_api_key"} if user_input is not None else {},
        )

    async def async_step_import(self, user_input) -> FlowResult:
        api_key = user_input.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            return self.async_abort(reason="no_api_key")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Weekly Meal Planner", data={"api_key": api_key.strip()}
        )
