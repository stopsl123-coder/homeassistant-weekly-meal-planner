<div align="center">

# Weekly Meal Planner

### Wochenplanung, Nährwerte und Einkaufsliste direkt in Home Assistant

Plane Frühstück, Mittag- und Abendessen für diese und nächste Woche. Rezepte
bleiben lokal gespeichert; die Einkaufsliste wird automatisch aus deinen Plänen
berechnet.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge)](https://hacs.xyz/)
[![Latest release](https://img.shields.io/github/v/release/stopsl123-coder/homeassistant-weekly-meal-planner?style=for-the-badge)](https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner/releases)
[![Tests](https://img.shields.io/github/actions/workflow/status/stopsl123-coder/homeassistant-weekly-meal-planner/release.yml?branch=main&label=Tests&style=for-the-badge)](https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner/actions)

</div>

---

## Auf einen Blick

| Wochenplan | Rezepte | Einkaufsliste |
| --- | --- | --- |
| Sieben Tage mit Frühstück, Mittag- und Abendessen | Rezepte mit Portionen, Zutaten und Nährwerten speichern | Zutaten kompatibler Einheiten zusammenfassen |
| Zwischen aktueller und nächster Woche wechseln | Gerichte je Mahlzeit auswählen oder automatisch planen | Liste für ausgewählte Woche direkt in Karte sehen |
| Tageskalorien und native Kalender-Entity | Gerichte bearbeiten oder löschen | Sensoren für Dashboard und Automationen |

## Installation

1. In HACS **Benutzerdefinierte Repositories** öffnen, Repository-URL
   `https://github.com/stopsl123-coder/homeassistant-weekly-meal-planner`
   eintragen und Kategorie **Integration** auswählen.
2. **Weekly Meal Planner** installieren und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Weekly Meal Planner** suchen.
4. USDA FoodData Central API-Schlüssel eingeben. Kostenlosen Schlüssel unter
   <https://fdc.nal.usda.gov/api-key-signup.html> anfordern.
5. Lovelace-Kartendatei
   [`weekly_meal_planner.js`](www/weekly_meal_planner/weekly_meal_planner.js)
   nach `/config/www/weekly_meal_planner.js` kopieren.
6. Unter **Einstellungen → Dashboards → Ressourcen** `/local/weekly_meal_planner.js`
   als **JavaScript-Modul** hinzufügen.
7. Karte zum Dashboard hinzufügen:

   ```yaml
   type: custom:weekly-meal-planner-card
   ```

> **Hinweis:** Integration und Lovelace-Karte sind getrennte Bestandteile.
> Die Sensoren funktionieren auch ohne Karte; für Rezeptverwaltung und
> Wochenansicht wird die JavaScript-Ressource benötigt.

## So funktioniert die Planung

Die Karte zeigt Montag bis Sonntag und lässt dich zwischen aktueller und
nächster Woche wechseln. Du kannst Mahlzeiten einzeln belegen oder Mittag- und
Abendessen automatisch planen lassen. Manuell eingeplante Frühstücke bleiben
bei automatischer Planung erhalten.

Die Einkaufsliste gehört zur ausgewählten Woche. Zutatenmengen werden anhand
der Haushaltsportionen skaliert und nur innerhalb kompatibler Einheiten
zusammengefasst. Der native Home-Assistant-Kalender und die Kalorien-Sensoren
beziehen sich weiterhin auf die aktuelle Woche.

## Nährwerte und Datenquellen

Beim Suchen und Speichern von Zutaten nutzt die Integration USDA FoodData
Central. Die Zutatenbezeichnungen werden dazu an USDA übertragen. Nährwerte
werden pro Portion berechnet. Wenn Einheit oder Nährwert fehlen, wird die
Summe als unvollständig angezeigt statt geschätzt.

Aktuell ist keine deutsche Zutaten- oder Fertiggerichte-Datenbank eingebunden.
Open Food Facts eignet sich für verpackte Markenprodukte, aber nicht als
verlässliche Rezeptdatenbank. Die Datenbank steht unter ODbL; bei einer
Integration wären Quellenhinweis und Share-Alike-Pflichten zu beachten. Der
deutsche Bundeslebensmittelschlüssel (BLS) ist fachlich passend für
Lebensmittel-Nährwerte, wird aber lizenziert bereitgestellt; eine freie
öffentliche API ist nicht dokumentiert. Fertiggericht-Rezeptdaten benötigen
eine gesonderte Prüfung von API-Zugang und Nutzungsrechten.

## Home-Assistant-Entities

- `sensor.weekly_meal_planner_shopping_list`: Anzahl der Positionen; Zutaten
  und Mengen stehen im Attribut `items` für die aktuelle Woche.
- `sensor.weekly_meal_planner_calories`: Wochenkalorien, Tageswerte, Makros
  und geplanter Essensplan der aktuellen Woche.
- `calendar.weekly_meal_planner`: geplante Mahlzeiten im nativen Kalender.

Beispiel für die Kalenderkarte:

```yaml
type: calendar
entities:
  - calendar.weekly_meal_planner
```

## Einstellungen und Hilfe

Unter **Einstellungen → Geräte & Dienste → Weekly Meal Planner → Optionen**
kannst du API-Schlüssel, Kalorienziel, Haushaltsportionen und ausgeschlossene
Zutaten anpassen. Rezepte und Wochenpläne bleiben in
`/config/mealplanner.db` gespeichert.

Die vollständige Anleitung mit Rezeptverwaltung, Services und Fehlerbehebung
steht in [docs/ANLEITUNG.md](docs/ANLEITUNG.md).

## Entwicklung

```sh
python -m pip install -r requirements_test.txt
python -m pytest -q
```
