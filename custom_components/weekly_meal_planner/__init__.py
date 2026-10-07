import logging
from homeassistant.core import HomeAssistant, ServiceCall

from .database import add_meal
from .mealplanner import generate_shopping_list, week_plan
from .smart_planner import generate_simple_week_plan

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config):
    async def handle_add_meal(call: ServiceCall):
        name = call.data["name"]
        meal_type = call.data["meal_type"]
        ingredients = call.data["ingredients"]
        add_meal(name, meal_type, ingredients)

    async def handle_generate_shopping_list(call: ServiceCall):
        _LOGGER.info("Einkaufsliste neu berechnet: %s", generate_shopping_list())

    async def handle_generate_week_plan(call: ServiceCall):
        new_plan = generate_simple_week_plan()
        week_plan.clear()
        week_plan.update(new_plan)
        _LOGGER.info("Neuer Wochenplan: %s", week_plan)

    hass.services.async_register("weekly_meal_planner", "add_meal", handle_add_meal)
    hass.services.async_register("weekly_meal_planner", "generate_shopping_list", handle_generate_shopping_list)
    hass.services.async_register("weekly_meal_planner", "generate_week_plan", handle_generate_week_plan)

    return True
