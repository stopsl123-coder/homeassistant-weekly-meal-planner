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
4. USDA FoodData Central API-Schlüssel optional eintragen. BLS 4.0 funktioniert
   ohne Schlüssel; USDA kannst du als alternative Datenquelle auswählen.
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

Beim Suchen und Speichern von Zutaten nutzt die Integration standardmäßig den
deutschen Bundeslebensmittelschlüssel (BLS) 4.0. USDA FoodData Central ist eine
optionale alternative Datenquelle.
Bei der ersten BLS-Suche lädt Home Assistant das offizielle Datenarchiv
(ca. 14 MB) herunter und importiert es lokal in `/config/mealplanner.db`.
Danach funktioniert die Suche lokal. BLS 4.0 umfasst 7.140 Lebensmittel und
138 Nährstoffe; die Daten stehen unter CC BY 4.0. Quellenangabe:
Max Rubner-Institut (2025), Bundeslebensmittelschlüssel 4.0, DOI
[10.25826/Data20251217-134202-0](https://doi.org/10.25826/Data20251217-134202-0).

Die Rezeptsuche verwendet TheMealDB und zeigt Namen, Zutaten, Mengen,
Zubereitung und Quelle. Importierte Mengen musst du prüfen; Angaben wie
„to taste“ werden nicht geschätzt. Wähle für jede Zutat den passenden
BLS-Nährwerttreffer, bevor du das Gericht speicherst. Die Zubereitung und
Quellenangabe bleiben am gespeicherten Rezept.

TheMealDB-Rezepte können englisch sein; der Suchdienst verlangt laut Anbieter
Unterstützerstatus für öffentliche App-Store-Veröffentlichungen. Rezeptdaten
werden nicht in die Integration gebündelt, sondern bei Bedarf von TheMealDB
abgerufen. Für USDA-Suchen werden Zutatenbegriffe an USDA übertragen. Fehlen
Einheit oder Nährwert, wird Summe als unvollständig angezeigt statt geschätzt.

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
