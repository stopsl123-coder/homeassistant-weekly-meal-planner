# Weekly Meal Planner

Home-Assistant-Integration zum Speichern von Rezepten, Planen von Mittag- und
Abendessen, Berechnen von Nährwerten und Erstellen einer Einkaufsliste.

## Funktionen

- Rezepte und Wochenpläne in `/config/mealplanner.db`.
- Nährwertabfrage bei USDA FoodData Central beim Speichern eines Rezepts.
- Sensoren für Anzahl der Einkaufslistenpositionen sowie Wochenkalorien und
  Makros.
- Einkaufsmenge wird nur bei kompatiblen Einheiten umgerechnet und summiert.
- Lovelace-Karte zum Eingeben von Rezepten und Ausführen der Planer-Aktionen.

Beim Speichern werden Zutatenbezeichnungen an USDA FoodData Central gesendet.
Ein gültiger API-Schlüssel und Internetzugang sind dafür erforderlich.
Nährwertsummen bleiben unbekannt, wenn Zutatenmenge nicht in Gewicht
umgerechnet werden kann oder Nährwerte fehlen. Volumen wird nicht pauschal mit
Gewicht gleichgesetzt.

## Installation

1. Dieses Repository in HACS als benutzerdefinierte **Integration** installieren.
2. Home Assistant neu starten und **Weekly Meal Planner** unter Einstellungen >
   Geräte & Dienste hinzufügen.
3. USDA-FoodData-Central-API-Schlüssel eingeben. Schlüssel gibt es unter
   <https://fdc.nal.usda.gov/api-key-signup.html>.
4. `www/weekly_meal_planner/weekly_meal_planner.js` nach `/config/www/` als
   `weekly_meal_planner.js` kopieren.
5. `/local/weekly_meal_planner.js` als JavaScript-Modul-Dashboard-Ressource
   registrieren und diese Karte hinzufügen:

   ```yaml
   type: custom:weekly-meal-planner-card
   ```

Die Karte speichert Rezepte, erstellt Wochenpläne und aktualisiert den
Einkaufslisten-Sensor. Die Integration erstellt
`sensor.weekly_meal_planner_shopping_list` und
`sensor.weekly_meal_planner_calories`.

Eine vorhandene YAML-Konfiguration mit `weekly_meal_planner: api_key:` wird
automatisch in einen Config-Entry importiert. Den YAML-Block nach dem Neustart
entfernen.

## Services

`weekly_meal_planner.add_meal` erwartet Rezeptname, Mahlzeitentyp
(`breakfast`, `lunch` oder `dinner`) und Zutaten:

```yaml
name: Hähnchen mit Reis
meal_type: dinner
ingredients:
  Hähnchen:
    amount: 200
    unit: g
  Reis:
    amount: 150
    unit: g
```

Zutatenmengen gelten jeweils für eine geplante Portion.
`weekly_meal_planner.generate_week_plan` verteilt gespeicherte Mittags- und
Abendessen-Rezepte auf die aktuelle Woche von Montag bis Sonntag.
`weekly_meal_planner.generate_shopping_list` aktualisiert Einkaufslisten- und
Nährwertsensoren.

## Entwicklung

Tests ausführen:

```sh
python -m unittest discover -s tests -v
```

GitHub Actions kompiliert die Integration und führt diese Tests bei Pushes und
Pull Requests aus.
