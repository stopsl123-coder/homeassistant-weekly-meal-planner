#!/bin/bash

echo "Erstelle Verzeichnisstruktur..."
mkdir -p custom_components/weekly_meal_planner
mkdir -p www/weekly_meal_planner

##############################################
# manifest.json
##############################################
cat > custom_components/weekly_meal_planner/manifest.json << 'EOF'
{
  "domain": "weekly_meal_planner",
  "name": "Weekly Meal Planner",
  "version": "1.0.0",
  "documentation": "https://example.com/weekly_meal_planner",
  "requirements": ["requests"],
  "codeowners": ["@thomas"],
  "iot_class": "local_polling"
}
EOF

##############################################
# services.yaml
##############################################
cat > custom_components/weekly_meal_planner/services.yaml << 'EOF'
add_meal:
  description: Fügt ein neues Gericht zur Datenbank hinzu
  fields:
    name:
      description: Name des Gerichts
      example: "Hähnchen mit Reis"
    meal_type:
      description: Art der Mahlzeit
      example: "lunch"
    ingredients:
      description: Zutaten als JSON
      example: '{"Hähnchen": {"amount": 200, "unit": "g"}, "Reis": {"amount": 150, "unit": "g"}}'

generate_shopping_list:
  description: Generiert die Einkaufsliste

generate_week_plan:
  description: Erzeugt einen einfachen Wochenplan nach Kalorienziel
EOF

##############################################
# __init__.py
##############################################
cat > custom_components/weekly_meal_planner/__init__.py << 'EOF'
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
EOF

##############################################
# nutrition_api.py
##############################################
cat > custom_components/weekly_meal_planner/nutrition_api.py << 'EOF'
import requests

API_KEY = "DEIN_API_KEY_HIER"
BASE_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

def get_nutrition_for_item(item_name):
    params = {
        "api_key": API_KEY,
        "query": item_name,
        "pageSize": 1
    }

    response = requests.get(BASE_URL, params=params)
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
cat > custom_components/weekly_meal_planner/database.py << 'EOF'
import sqlite3
import json

DB_PATH = "/config/mealplanner.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY,
            name TEXT,
            ingredients TEXT,
            meal_type TEXT
        )
    """)

    example_meals = [
        (
            "Rührei mit Toast",
            json.dumps({
                "Eier": {"amount": 3, "unit": "Stück", "calories": 72},
                "Toast": {"amount": 2, "unit": "Stück", "calories": 80},
                "Butter": {"amount": 10, "unit": "g", "calories": 75}
            }),
            "breakfast"
        ),
        (
            "Spaghetti Bolognese",
            json.dumps({
                "Spaghetti": {"amount": 200, "unit": "g", "calories": 350},
                "Hackfleisch": {"amount": 300, "unit": "g", "calories": 250},
                "Tomatensauce": {"amount": 250, "unit": "ml", "calories": 70}
            }),
            "lunch"
        ),
        (
            "Gemüsepfanne",
            json.dumps({
                "Paprika": {"amount": 2, "unit": "Stück", "calories": 30},
                "Zucchini": {"amount": 1, "unit": "Stück", "calories": 20},
                "Reis": {"amount": 150, "unit": "g", "calories": 180}
            }),
            "dinner"
        )
    ]

    for meal in example_meals:
        c.execute("INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)", meal)

    conn.commit()
    conn.close()

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

    if row:
        return json.loads(row[0])
    return {}
EOF

##############################################
# mealplanner.py
##############################################
cat > custom_components/weekly_meal_planner/mealplanner.py << 'EOF'
from .database import get_ingredients

week_plan = {
    "monday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "tuesday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "wednesday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "thursday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "friday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "saturday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"},
    "sunday": {"breakfast": "Rührei mit Toast", "lunch": "Spaghetti Bolognese", "dinner": "Gemüsepfanne"}
}

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
                    if shopping_list[item]["unit"] == unit:
                        shopping_list[item]["amount"] += amount
                    else:
                        key = item + f" ({unit})"
                        if key not in shopping_list:
                            shopping_list[key] = {"amount": amount, "unit": unit}
                        else:
                            shopping_list[key]["amount"] += amount

    return shopping_list

def calculate_calories_for_meal(meal_name):
    ingredients = get_ingredients(meal_name)
    total_calories = 0

    for item, data in ingredients.items():
        amount = data["amount"]
        unit = data["unit"]
        calories = data.get("calories", 0)

        if unit in ["g", "ml"]:
            total_calories += (calories / 100) * amount
        elif unit == "Stück":
            total_calories += calories * amount

    return round(total_calories, 2)
EOF

##############################################
# smart_planner.py
##############################################
cat > custom_components/weekly_meal_planner/smart_planner.py << 'EOF'
from .database import get_meals
from .mealplanner import calculate_calories_for_meal

DAILY_TARGET_KCAL = 2000

def generate_simple_week_plan():
    meals = get_meals()
    lunch_dinner = [m for m in meals if m["meal_type"] in ["lunch", "dinner"]]

    week_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    new_plan = {}

    idx = 0
    for day in week_days:
        day_total = 0
        day_meals = {"breakfast": "Rührei mit Toast"}

        if idx < len(lunch_dinner):
            meal_lunch = lunch_dinner[idx]["name"]
            kcal_lunch = calculate_calories_for_meal(meal_lunch)
            day_meals["lunch"] = meal_lunch
            day_total += kcal_lunch
            idx += 1

        if idx < len(lunch_dinner):
            meal_dinner = lunch_dinner[idx]["name"]
            kcal_dinner = calculate_calories_for_meal(meal_dinner)
            if day_total + kcal_dinner <= DAILY_TARGET_KCAL * 1.3:
                day_meals["dinner"] = meal_dinner
                day_total += kcal_dinner
                idx += 1
            else:
                day_meals["dinner"] = "Gemüsepfanne"

        new_plan[day] = day_meals

    return new_plan
EOF

##############################################
# sensor.py
##############################################
cat > custom_components/weekly_meal_planner/sensor.py << 'EOF'
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
# Frontend JS
##############################################
cat > www/weekly_meal_planner/weekly_meal_planner.js << 'EOF'
class WeeklyMealPlannerCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.rendered) {
      this.render();
      this.rendered = true;
    }
  }

  render() {
    this.innerHTML = `
      <style>
        .meal-form { margin: 10px 0; padding: 10px; border: 1px solid #ccc; }
        .ingredient-row { display: flex; gap: 5px; margin-bottom: 5px; }
        .ingredient-row input { flex: 1; }
        .day { padding: 10px; border-bottom: 1px solid #ccc; }
        .title { font-weight: bold; }
      </style>

      <div class="meal-form">
        <h3>Neues Gericht anlegen</h3>
        <input id="meal_name" placeholder="Name des Gerichts">
        <input id="meal_type" placeholder="meal_type (breakfast/lunch/dinner)">

        <div id="ingredients_container"></div>
        <button id="add_ingredient">Zutat hinzufügen</button>
        <br><br>
        <button id="save_meal">Gericht speichern</button>
      </div>

      <button id="auto_plan">Automatisch Wochenplan erstellen</button>
      <button id="regen_list">Einkaufsliste neu berechnen</button>
    `;

    const container = this.querySelector("#ingredients_container");
    const addBtn = this.querySelector("#add_ingredient");
    addBtn.onclick = () => {
      const row = document.createElement("div");
      row.className = "ingredient-row";
      row.innerHTML = `
        <input placeholder="Zutat (z.B. Eier)">
        <input placeholder="Menge (z.B. 3)">
        <input placeholder="Einheit (Stück/g/ml)">
      `;
      container.appendChild(row);
    };

    this.querySelector("#save_meal").onclick = () => {
      const name = this.querySelector("#meal_name").value;
      const meal_type = this.querySelector("#meal_type").value;

      const rows = container.querySelectorAll(".ingredient-row");
      const ingredients = {};

      rows.forEach(row => {
        const inputs = row.querySelectorAll("input");
        const item = inputs[0].value;
        const amount = parseFloat(inputs[1].value);
        const unit = inputs[2].value;

        if (item && !isNaN(amount) && unit) {
          ingredients[item] = { amount, unit };
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
# CSS
##############################################
cat > www/weekly_meal_planner/weekly_meal_planner.css << 'EOF'
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

echo "Alle Dateien wurden erfolgreich erstellt und befüllt!"
