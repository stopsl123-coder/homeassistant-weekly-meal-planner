# Weekly Meal Planner

Home-Assistant-Integration zum Speichern von Rezepten, Planen von Mittag- und
Abendessen, Berechnen von Nährwerten und Erstellen einer Einkaufsliste.

## Funktionen

- Rezepte und Wochenpläne in `/config/mealplanner.db`.
- Nährwertabfrage bei USDA FoodData Central beim Speichern eines Rezepts.
- Sensoren für Anzahl der Einkaufslistenpositionen sowie Wochenkalorien und
  Makros.
- Einen nativen Home-Assistant-Kalender mit einer Tagesübersicht der geplanten
  Mittag- und Abendessen.
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
`sensor.weekly_meal_planner_calories` sowie `calendar.weekly_meal_planner`.

Den Essensplan zusammen mit Kalenderwochen und Feiertagen in einer nativen
Kalenderkarte anzeigen:

```yaml
type: calendar
entities:
  - calendar.weekly_meal_planner
  - calendar.kalenderwochen
  - calendar.feiertage_in_deutschland
```

Die native Kalenderkarte benötigt keine Lovelace-Custom-Card-Ressource. Die
Rezeptkarte bleibt separat und wird wie oben beschrieben manuell registriert.

Unter **Einstellungen > Geräte & Dienste > Weekly Meal Planner > Optionen**
können API-Schlüssel, tägliches Kalorienziel, Haushaltsportionen und
ausgeschlossene Zutaten konfiguriert werden. Das Kalorienziel bezieht sich auf
die geplanten Mittag- und Abendessen zusammen; Frühstück ist nicht Teil des
automatischen Wochenplans. Rezeptzutaten beschreiben Gesamtmengen für die
gespeicherte Rezept-Portionenzahl. Nährwerte werden pro Portion berechnet und
Einkaufsmengen auf Haushaltsportionen skaliert.

Eine vorhandene YAML-Konfiguration mit `weekly_meal_planner: api_key:` wird
automatisch in einen Config-Entry importiert. Den YAML-Block nach dem Neustart
entfernen.

## Services

`weekly_meal_planner.add_meal` erwartet Rezeptname, Mahlzeitentyp
(`breakfast`, `lunch` oder `dinner`) und Zutaten:

```yaml
name: Hähnchen mit Reis
meal_type: dinner
servings: 2
ingredients:
  Hähnchen:
    amount: 200
    unit: g
  Reis:
    amount: 150
    unit: g
```

Zutatenmengen beschreiben Gesamtmengen für `servings` Rezeptportionen
(`servings` ist standardmäßig 1). Nährwerte werden pro Portion berechnet.
`weekly_meal_planner.generate_week_plan` verteilt gespeicherte Mittags- und
Abendessen-Rezepte auf die aktuelle Woche von Montag bis Sonntag.
`weekly_meal_planner.generate_shopping_list` aktualisiert Einkaufslisten- und
Nährwertsensoren.

## Entwicklung

Testabhängigkeiten installieren und Tests ausführen:

```sh
python -m pip install -r requirements_test.txt
python -m pytest -q
```

GitHub Actions kompiliert die Integration und führt Unit- und
Home-Assistant-Integrationstests bei Pushes und Pull Requests aus.
