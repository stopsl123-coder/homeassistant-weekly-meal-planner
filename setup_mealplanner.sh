#!/bin/bash

mkdir -p custom_components/weekly_meal_planner
mkdir -p www/weekly_meal_planner

touch custom_components/weekly_meal_planner/__init__.py
touch custom_components/weekly_meal_planner/manifest.json
touch custom_components/weekly_meal_planner/services.yaml
touch custom_components/weekly_meal_planner/database.py
touch custom_components/weekly_meal_planner/nutrition_api.py
touch custom_components/weekly_meal_planner/mealplanner.py
touch custom_components/weekly_meal_planner/smart_planner.py
touch custom_components/weekly_meal_planner/sensor.py

touch www/weekly_meal_planner/weekly_meal_planner.js
touch www/weekly_meal_planner/weekly_meal_planner.css

echo "Verzeichnisstruktur für Weekly Meal Planner wurde erfolgreich erstellt."
