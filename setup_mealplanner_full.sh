#!/bin/bash
set -e

echo "Starte Full-Setup für HACS-Repository..."

REPO_URL="https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner"
DOMAIN="weekly_meal_planner"

mkdir -p custom_components/$DOMAIN
mkdir -p custom_components/$DOMAIN/translations
mkdir -p www/$DOMAIN
mkdir -p .github/workflows

##############################################
# info.md (HACS-Info)
##############################################
cat > info.md << 'EOF'
# Weekly Meal Planner

Der **Weekly Meal Planner** ist eine Home-Assistant-Integration zur Planung von Wochenmahlzeiten,
Einkaufslisten und Kalorien-/Makro-Tracking.

## Features

- Automatische Wochenplanung (Lunch/Dinner)
- Einkaufslisten-Generierung
- Kalorien- und Makro-Berechnung
- USDA FoodData Central API-Unterstützung
- Lovelace Custom Card zur Eingabe neuer Gerichte
- Sensoren für Kalorien und Einkaufsliste

## Installation (HACS Custom Repository)

1. HACS öffnen → Integrationen
2. Rechts oben: ⋮ → Custom repositories
3. Repository-URL:

   `https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner`

4. Kategorie: `Integration`
5. Installation durchführen, Home Assistant neu starten

## Konfiguration

In `configuration.yaml`:

```yaml
weekly_meal_planner:
  api_key: !secret usda_api_key


EOF



##############################################

#GitHub Release Workflow
##############################################
cat > .github/workflows/release.yml << 'EOF'
name: Release

on:
push:
tags:
- 'v..*'

jobs:
build:
runs-on: ubuntu-latest
steps:
- name: Checkout
uses: actions/checkout@v4

name: Set up Python
uses: actions/setup-python@v5
with:
python-version: '3.11'

name: Run basic checks
run: |
python -m compileall custom_components
EOF

##############################################

#Versionierung (version.py)
##############################################
cat > custom_components/$DOMAIN/version.py << 'EOF'
version = "1.1.0"
EOF

##############################################

#manifest.json aktualisieren
##############################################
cat > custom_components/$DOMAIN/manifest.json << EOF
{
"domain": "$DOMAIN",
"name": "Weekly Meal Planner",
"version": "1.1.0",
"documentation": "$REPO_URL",
"requirements": ["requests"],
"codeowners": ["@stopsl123-coder"],
"iot_class": "local_polling",
"config_flow": true
}
EOF
##############################################
# Config-Flow UI (config_flow.py)
##############################################
cat > custom_components/$DOMAIN/config_flow.py << 'EOF'
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
EOF

##############################################
# const.py
##############################################
cat > custom_components/$DOMAIN/const.py << 'EOF'
DOMAIN = "weekly_meal_planner"
EOF

##############################################
# translations/strings.json
##############################################
cat > custom_components/$DOMAIN/strings.json << 'EOF'
{
  "config": {
    "step": {
      "user": {
        "title": "Weekly Meal Planner",
        "description": "Bitte gib deinen USDA FoodData Central API-Key ein."
      }
    },
    "error": {
      "no_api_key": "API-Key darf nicht leer sein."
    }
  }
}
EOF

##############################################
# translations/de.json
##############################################
cat > custom_components/$DOMAIN/translations/de.json << 'EOF'
{
  "config": {
    "step": {
      "user": {
        "title": "Weekly Meal Planner",
        "description": "Bitte gib deinen USDA FoodData Central API-Key ein."
      }
    },
    "error": {
      "no_api_key": "API-Key darf nicht leer sein."
    }
  }
}
EOF

##############################################
# translations/en.json
##############################################
cat > custom_components/$DOMAIN/translations/en.json << 'EOF'
{
  "config": {
    "step": {
      "user": {
        "title": "Weekly Meal Planner",
        "description": "Please enter your USDA FoodData Central API key."
      }
    },
    "error": {
      "no_api_key": "API key must not be empty."
    }
  }
}
EOF

##############################################
# __init__.py anpassen für Config-Flow
##############################################
cat > custom_components/$DOMAIN/__init__.py << 'EOF'
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
EOF

##############################################
# nutrition_api.py
##############################################
cat > custom_components/$DOMAIN/nutrition_api.py << 'EOF'
import requests

API_KEY = None

def set_api_key(key):
    global API_KEY
    API_KEY = key

def get_nutrition_for_item(item_name):
    if not API_KEY:
        raise RuntimeError("USDA API-Key nicht gesetzt!")

    params = {
        "api_key": API_KEY,
        "query": item_name,
        "pageSize": 1
    }

    response = requests.get("https://api.nal.usda.gov/fdc/v1/foods/search", params=params)
    response.raise_for_status()
    data = response.json()

    if "foods" not in data or len(data["foods"]) == 0:
        return None

    food = data["foods"][0]
    nutrients = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}

    return {
        "calories_per_100g": nutrients.get("Energy", 0),
        "protein": nutrients.get("Protein", 0),
        "fat": nutrients.get("Total lipid (fat)", 0),
        "carbs": nutrients.get("Carbohydrate, by difference", 0)
    }
EOF

##############################################
# database.py
##############################################
cat > custom_components/$DOMAIN/database.py << 'EOF'
import sqlite3
import json

DB_PATH = "/config/mealplanner.db"

def add_meal(name, meal_type, ingredients_json):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)",
        (name, ingredients_json, meal_type)
    )
    conn.commit()
    conn.close()

def get_meals():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, ingredients, meal_type FROM meals")
    rows = c.fetchall()
    conn.close()
    return [{"name": r[0], "ingredients": json.loads(r[1]), "meal_type": r[2]} for r in rows]

def get_ingredients(meal_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ingredients FROM meals WHERE name=?", (meal_name,))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row else {}
EOF

##############################################
# mealplanner.py
##############################################
cat > custom_components/$DOMAIN/mealplanner.py << 'EOF'
from .database import get_ingredients

week_plan = {}

def generate_shopping_list():
    shopping_list = {}
    for day, meals in week_plan.items():
        for meal_type, meal_name in meals.items():
            ingredients = get_ingredients(meal_name)
            for item, data in ingredients.items():
                amount = data["amount"]
                unit = data["unit"]
                if item not in shopping_list:
                    shopping_list[item] = {"amount": amount, "unit": unit}
                else:
                    shopping_list[item]["amount"] += amount
    return shopping_list

def calculate_calories_for_meal(meal_name):
    ingredients = get_ingredients(meal_name)
    total = 0
    for item, data in ingredients.items():
        amount = data["amount"]
        unit = data["unit"]
        calories = data.get("calories", 0)
        if unit in ["g", "ml"]:
            total += (calories / 100) * amount
        else:
            total += calories * amount
    return round(total, 2)
EOF

##############################################
# smart_planner.py
##############################################
cat > custom_components/$DOMAIN/smart_planner.py << 'EOF'
from .database import get_meals
from .mealplanner import calculate_calories_for_meal

DAILY_TARGET_KCAL = 2000

def generate_simple_week_plan():
    meals = get_meals()
    lunch_dinner = [m for m in meals if m["meal_type"] in ["lunch", "dinner"]]
    week_days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    new_plan = {}
    idx = 0

    for day in week_days:
        day_total = 0
        day_meals = {"breakfast": "Rührei mit Toast"}

        if idx < len(lunch_dinner):
            lunch = lunch_dinner[idx]["name"]
            day_meals["lunch"] = lunch
            day_total += calculate_calories_for_meal(lunch)
            idx += 1

        if idx < len(lunch_dinner):
            dinner = lunch_dinner[idx]["name"]
            kcal = calculate_calories_for_meal(dinner)
            if day_total + kcal <= DAILY_TARGET_KCAL * 1.3:
                day_meals["dinner"] = dinner
                idx += 1
            else:
                day_meals["dinner"] = "Gemüsepfanne"

        new_plan[day] = day_meals

    return new_plan
EOF

##############################################
# sensor.py
##############################################
cat > custom_components/$DOMAIN/sensor.py << 'EOF'
from homeassistant.helpers.entity import Entity
from .mealplanner import generate_shopping_list, calculate_calories_for_meal, week_plan

WEEKLY_TARGET_KCAL = 14000

class ShoppingListSensor(Entity):
    @property
    def name(self):
        return "Weekly Meal Planner Shopping List"

    @property
    def state(self):
        return "bereit"

    @property
    def extra_state_attributes(self):
        return generate_shopping_list()

class MealCaloriesSensor(Entity):
    @property
    def name(self):
        return "Weekly Meal Planner Calories"

    @property
    def state(self):
        total = 0
        for day, meals in week_plan.items():
            for meal_type, meal_name in meals.items():
                total += calculate_calories_for_meal(meal_name)
        return round(total, 2)

    @property
    def extra_state_attributes(self):
        day_calories = {}
        total = 0
        for day, meals in week_plan.items():
            day_total = 0
            for meal_type, meal_name in meals.items():
                day_total += calculate_calories_for_meal(meal_name)
            day_calories[day] = round(day_total, 2)
            total += day_total

        return {
            "per_day": day_calories,
            "week_total": round(total, 2),
            "week_target": WEEKLY_TARGET_KCAL,
            "difference": round(total - WEEKLY_TARGET_KCAL, 2)
        }
EOF
##############################################
# Frontend: weekly_meal_planner.js
##############################################
cat > www/$DOMAIN/weekly_meal_planner.js << 'EOF'
class WeeklyMealPlannerCard extends HTMLElement {
  setConfig(config) { this.config = config; }
  set hass(hass) {
    this._hass = hass;
    if (!this.rendered) { this.render(); this.rendered = true; }
  }

  render() {
    this.innerHTML = `
      <style>
        .meal-form { margin: 10px; padding: 10px; border: 1px solid #ccc; }
        .ingredient-row { display: flex; gap: 5px; margin-bottom: 5px; }
        .ingredient-row input { flex: 1; }
      </style>

      <div class="meal-form">
        <h3>Neues Gericht</h3>
        <input id="meal_name" placeholder="Name">
        <input id="meal_type" placeholder="breakfast/lunch/dinner">

        <div id="ingredients_container"></div>
        <button id="add_ingredient">Zutat hinzufügen</button>
        <br><br>
        <button id="save_meal">Speichern</button>
      </div>

      <button id="auto_plan">Automatisch planen</button>
      <button id="regen_list">Einkaufsliste neu berechnen</button>
    `;

    const container = this.querySelector("#ingredients_container");
    this.querySelector("#add_ingredient").onclick = () => {
      const row = document.createElement("div");
      row.className = "ingredient-row";
      row.innerHTML = `
        <input placeholder="Zutat">
        <input placeholder="Menge">
        <input placeholder="Einheit">
      `;
      container.appendChild(row);
    };

    this.querySelector("#save_meal").onclick = () => {
      const name = this.querySelector("#meal_name").value;
      const meal_type = this.querySelector("#meal_type").value;

      const rows = container.querySelectorAll(".ingredient-row");
      const ingredients = {};

      rows.forEach(row => {
        const [item, amount, unit] = row.querySelectorAll("input");
        if (item.value && amount.value && unit.value) {
          ingredients[item.value] = {
            amount: parseFloat(amount.value),
            unit: unit.value
          };
        }
      });

      this._hass.callService("weekly_meal_planner", "add_meal", {
        name,
        meal_type,
        ingredients: JSON.stringify(ingredients)
      });
    };

    this.querySelector("#auto_plan").onclick = () => {
      this._hass.callService("weekly_meal_planner", "generate_week_plan", {});
    };

    this.querySelector("#regen_list").onclick = () => {
      this._hass.callService("weekly_meal_planner", "generate_shopping_list", {});
    };
  }
}

customElements.define("weekly-meal-planner-card", WeeklyMealPlannerCard);
EOF

##############################################
# Frontend: weekly_meal_planner.css
##############################################
cat > www/$DOMAIN/weekly_meal_planner.css << 'EOF'
.meal-form {
  background: #f7f7f7;
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 10px;
}

.ingredient-row {
  display: flex;
  gap: 5px;
  margin-bottom: 5px;
}

.ingredient-row input {
  flex: 1;
}
EOF

##############################################
# Abschluss
##############################################
echo "Full-Setup abgeschlossen. Bitte git add/commit/push ausführen."
echo "Dein Repository ist jetzt vollständig HACS-ready, mit Config-Flow, Release-Workflow, Versionierung und Frontend."

