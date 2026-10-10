from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class WeeklyMealPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Weekly Meal Planner."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return WeeklyMealPlannerOptionsFlow()

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


class WeeklyMealPlannerOptionsFlow(config_entries.OptionsFlow):
    """Configure API key, nutrition target, household size and exclusions."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            api_key = user_input.get("api_key", "").strip()
            if api_key:
                return self.async_create_entry(
                    title="",
                    data={
                        **user_input,
                        "api_key": api_key,
                        "target_kcal": int(user_input["target_kcal"]),
                        "household_servings": int(user_input["household_servings"]),
                    },
                )

        entry = self.config_entry
        schema = vol.Schema(
            {
                vol.Required("api_key"): str,
                vol.Required("target_kcal"): vol.All(
                    vol.Coerce(int), vol.Range(min=500, max=10_000)
                ),
                vol.Required("household_servings"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=20)
                ),
                vol.Optional("excluded_ingredients", default=""): str,
            }
        )
        defaults = {
            "api_key": entry.options.get("api_key", entry.data["api_key"]),
            "target_kcal": entry.options.get("target_kcal", 2000),
            "household_servings": entry.options.get("household_servings", 2),
            "excluded_ingredients": entry.options.get("excluded_ingredients", ""),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, defaults),
            errors={"base": "no_api_key"} if user_input is not None else {},
        )
