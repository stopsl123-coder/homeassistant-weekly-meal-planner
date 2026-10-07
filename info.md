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


