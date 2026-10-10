# Weekly Meal Planner: ausführliche Anleitung

Diese Anleitung erklärt, wie du die Integration in Home Assistant einrichtest,
Rezepte speicherst, einen Wochenplan erstellst und ihn zusammen mit Kalenderwochen
und Feiertagen im Dashboard anzeigst.

## 1. Integration einrichten

1. Installiere **Weekly Meal Planner** über HACS als benutzerdefinierte
   Integration.
2. Starte Home Assistant neu.
3. Öffne **Einstellungen > Geräte & Dienste > Integration hinzufügen**.
4. Suche nach **Weekly Meal Planner** und wähle die Integration aus.
5. Trage deinen USDA-FoodData-Central-API-Schlüssel ein. Einen Schlüssel
   erhältst du unter <https://fdc.nal.usda.gov/api-key-signup.html>.
6. Öffne nach dem Einrichten die Integration und wähle **Optionen**, um
   API-Schlüssel und Planungseinstellungen anzupassen.

Für USDA-Suchen benötigt Home Assistant Internetzugang. Ohne gültigen Schlüssel
lassen sich keine USDA-Nährwerttreffer für neue Rezepte abrufen.

## 2. Rezeptkarte zum Dashboard hinzufügen

Die Rezeptkarte ist eine separate Lovelace-Karte. Die Kalenderkarte aus
Home Assistant braucht diese Datei nicht; sie zeigt den gespeicherten
Essensplan auch ohne Rezeptkarte an.

1. Lade
   [`weekly_meal_planner.js`](../www/weekly_meal_planner/weekly_meal_planner.js)
   aus diesem Repository herunter.
2. Kopiere die Datei in Home Assistants `www`-Ordner und benenne sie
   `weekly_meal_planner.js`. Der vollständige Pfad lautet normalerweise:
   `/config/www/weekly_meal_planner.js`. Du kannst dafür beispielsweise das
   File editor Add-on oder Samba verwenden. Lege den Ordner `www` an, falls er
   noch nicht existiert.
3. Öffne **Einstellungen > Dashboards > Ressourcen**. Je nach Home-Assistant-
   Version erreichst du die Ressourcenverwaltung auch über das Menü des
   Dashboards.
4. Füge Ressource mit URL `/local/weekly_meal_planner.js` und Typ
   **JavaScript-Modul** hinzu.
5. Öffne dein Dashboard im Bearbeitungsmodus und füge manuelle Karte mit
   folgendem YAML hinzu:

   ```yaml
   type: custom:weekly-meal-planner-card
   ```

6. Speichere Dashboard. Wenn Karte nach dem Neuladen nicht erscheint, lade
   Browserseite mit `Strg+F5` neu und kontrolliere Pfad sowie Ressourcentyp.

## 3. Optionen festlegen

Öffne **Einstellungen > Geräte & Dienste > Weekly Meal Planner > Optionen**.

- **USDA-FoodData-Central-API-Schlüssel:** Schlüssel für Zutatensuchen.
- **Tägliches Kalorienziel:** Ziel für geplantes Mittag- und Abendessen
  zusammen. Es ist kein persönlicher medizinischer Ernährungsrat.
- **Portionen im Haushalt:** Anzahl der Portionen, für die Einkaufsmengen
  berechnet werden.
- **Ausgeschlossene Zutaten:** Zutatennamen durch Komma trennen, zum Beispiel
  `Erdnüsse, Sellerie`. Rezepte mit passendem Zutatennamen werden bei der
  automatischen Wochenplanung ausgeschlossen.

Der automatische Planer plant Mittag- und Abendessen. Frühstücksrezepte können
gespeichert und über die Frühstücks-Kacheln der Wochenübersicht manuell
eingeplant werden.

## 4. Erstes Rezept anlegen

1. Öffne das Dashboard mit der Rezeptkarte.
2. Trage bei **Gerichtname** einen Rezeptnamen ein, zum Beispiel
   `Linsencurry`.
3. Trage bei **Portionen pro Rezept** die Anzahl der Portionen ein, auf die
   sich die unten angegebenen Gesamtmengen beziehen. Beispiel: `4`, wenn
   Zutatenmengen für vier Portionen gelten.
4. Wähle **Mittagessen**, **Abendessen** oder **Frühstück**.
5. Klicke auf **Zutat hinzufügen**.
6. Trage Zutat, Menge und Einheit ein. Menge muss größer als null sein.
   Wählst du **Stück**, erscheint zusätzlich Feld **Gewicht pro Stück (g)**.
   Trage dort Gewicht eines einzelnen Stücks ein, zum Beispiel `60` für Ei.
7. Klicke in derselben Zeile auf **USDA-Treffer suchen**.
8. Wähle im angezeigten Auswahlfeld den passenden USDA-Eintrag. Wiederhole
   Schritte 5 bis 8 für jede Zutat.
9. Klicke auf **Gericht speichern**.

Beispiel für ein Rezept mit vier Portionen:

| Zutat | Gesamtmenge | Einheit |
| --- | ---: | --- |
| Rote Linsen | 300 | g |
| Kokosmilch | 400 | ml |
| Zwiebel | 2 | Stück |

Das bedeutet: Mengen gelten für vier Portionen, nicht für eine einzelne
Portion. Die Integration berechnet Nährwerte pro Rezeptportion und skaliert
Einkaufsmengen auf die eingestellte Haushaltsgröße.

USDA-Suchergebnisse können englische Bezeichnungen verwenden. Prüfe Beschreibung
und Nährwerte pro 100 g im Auswahlfeld, bevor du Treffer auswählst. Wenn du
Zutatennamen nach der Suche änderst, suche Treffer erneut.
Bei Einheit **Stück** zeigt Auswahlkarte zusätzlich geschätzte kcal pro Stück,
basierend auf eingegebenem Gewicht. Ohne dieses Gewicht kann Integration
Nährwerte dieser Zutat nicht berechnen. Die USDA-Datenbank liefert Angaben pro
100 g; Home Assistant übersetzt originale USDA-Bezeichnungen nicht automatisch.

### Hinweis zu Nährwerten und Einheiten

Nährwerte werden zuverlässig aus Zutaten berechnet, deren Menge als Gewicht
vorliegt, beispielsweise `g`, `kg` oder `mg`. Bei **Stück** musst du zusätzlich
Gewicht eines Stücks angeben, damit Integration USDA-Werte pro 100 g auf
Stückzahl umrechnen kann. Volumen wie `ml` wird nicht pauschal in Gramm
umgerechnet. Fehlen erforderliche Gewichte oder USDA-Nährwerte, können Tages-
und Wochensummen als nicht verfügbar erscheinen. Einkaufsliste kann Mengen
trotzdem anzeigen.

## 5. Weitere Rezepte und Änderungen

Lege jedes Rezept einzeln mit der Rezeptkarte an. Wenn du ein gespeichertes
Rezept mit demselben Namen erneut speicherst, wird es aktualisiert, nicht als
zweites Rezept angelegt. Zutaten, Mahlzeitentyp und Portionenzahl werden dabei
durch neue Werte ersetzt.

Die Rezepte und Wochenpläne bleiben in `/config/mealplanner.db` gespeichert.
Ein Neustart von Home Assistant löscht sie nicht.

## 6. Wochenplan erzeugen

1. Speichere zuerst mindestens ein Rezept vom Typ **Mittagessen** oder
   **Abendessen**.
2. Klicke in der Rezeptkarte auf **Woche automatisch planen**.
3. Der Planer füllt die aktuelle Woche von Montag bis Sonntag mit Mittag- und
   Abendessen. Ausgeschlossene Zutaten, Kalorienziel und kürzlich verwendete
   Rezepte fließen in die Auswahl ein.
4. Die Wochenübersicht erscheint in der Rezeptkarte. Der Kalender und die
   Sensoren werden ebenfalls aktualisiert.

Erneutes Erstellen ersetzt den gespeicherten Plan für die aktuelle Woche.
Gespeicherte Rezepte und manuell geplante Frühstücke bleiben erhalten.

Die Wochenübersicht zeigt Montag bis Sonntag mit je einer Kachel für Frühstück,
Mittagessen und Abendessen. Klicke auf eine Kachel, um gespeicherte Gerichte
des passenden Typs auszuwählen und zu übernehmen. Freie Kacheln lassen sich
genauso belegen. **Neues Gericht anlegen** öffnet Rezeptformular; startest du
es aus einer Kachel, wird neues Gericht nach dem Speichern direkt dort
eingeplant. Änderungen gelten nur für aktuelle Woche; nativer Kalender wird
ebenfalls aktualisiert.

Neben geplanten Gerichten stehen berechnete kcal pro Portion. Summe basiert auf
Nährwerten aller Zutaten geteilt durch Rezeptportionen. Gerichte mit fehlenden
Gewichtsangaben zeigen keine Kalorienzahl. Automatische Planung erzeugt
Mittag- und Abendessen, lässt manuell geplante Frühstücke aber bestehen.

## 7. Essensplan im Home-Assistant-Kalender anzeigen

Füge native **Kalender**-Karte zum Dashboard hinzu und verwende:

```yaml
type: calendar
entities:
  - calendar.weekly_meal_planner
  - calendar.kalenderwochen
  - calendar.feiertage_in_deutschland
```

Behalte dort die Kalender-Entity-IDs bei, die in deiner Installation bereits
funktionieren. `calendar.weekly_meal_planner` zeigt pro geplantem Tag
Mittag- und Abendessen als Ganztagstermin. Der Kalender bleibt leer, bis du
Wochenplan erstellt hast. Für Anzeige über mehrere Wochen kannst du
Kalenderkarte beispielsweise auf `type: calendar` und `initial_view: listWeek`
konfigurieren:

```yaml
type: calendar
initial_view: listWeek
entities:
  - calendar.weekly_meal_planner
  - calendar.kalenderwochen
  - calendar.feiertage_in_deutschland
```

Die `initial_view`-Option hängt von deiner Home-Assistant-Version ab. Wenn sie
nicht unterstützt wird, entferne diese Zeile.

## 8. Alternative: Rezept über Entwicklerwerkzeuge speichern

Du kannst statt Rezeptkarte auch Home-Assistant-Aktion
`weekly_meal_planner.add_meal` ausführen:

1. Öffne **Entwicklerwerkzeuge > Aktionen**.
2. Wähle Aktion `weekly_meal_planner.add_meal`.
3. Füge Daten ein und führe Aktion aus:

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

Wenn keine `fdc_id` angegeben ist, sucht Integration automatisch nach
USDA-Treffern und verwendet ersten passenden Treffer. Für gezielte Auswahl
empfiehlt sich Rezeptkarte. Gültige Mahlzeitentypen sind `breakfast`, `lunch`
und `dinner`; `servings` muss zwischen 1 und 100 liegen. Jede Zutat braucht
positive `amount` und `unit`.

Weitere Aktionen findest du ebenfalls unter **Entwicklerwerkzeuge > Aktionen**:

- `weekly_meal_planner.generate_week_plan`: aktuelle Woche neu planen.
- `weekly_meal_planner.generate_shopping_list`: Sensoren für gespeicherten
  Plan aktualisieren.
- `weekly_meal_planner.search_ingredient`: USDA-Treffer suchen. Datenbeispiel:

  ```yaml
  query: brown rice
  force_refresh: false
  ```

## 9. Einkaufsliste und Sensoren

Integration stellt diese Entities bereit:

- `sensor.weekly_meal_planner_shopping_list`: Anzahl der Einkaufspositionen.
  Die einzelnen Zutaten und Mengen stehen in Attribut `items`.
- `sensor.weekly_meal_planner_calories`: Wochensumme der Kalorien, sofern
  Nährwerte vollständig berechenbar sind. Tageswerte, Makros und fehlende
  Zutaten stehen in Attributen.
- `calendar.weekly_meal_planner`: geplante Mahlzeiten als Kalenderereignisse.

Du kannst Sensoren über **Einstellungen > Geräte & Dienste > Entitäten** suchen
und anschließend als Entitäts- oder Markdown-Karte ins Dashboard legen.

## 10. Fehlerbehebung

- **Rezeptkarte wird nicht gefunden:** Kontrolliere, ob Datei unter
  `/config/www/weekly_meal_planner.js` liegt und Ressource als JavaScript-Modul
  mit URL `/local/weekly_meal_planner.js` registriert ist. Danach Browsercache
  mit `Strg+F5` leeren.
- **USDA-Suche schlägt fehl:** Prüfe API-Schlüssel unter Integration-Optionen,
  Internetverbindung des Home Assistant und Schreibweise der Zutat. Bei
  mehrdeutigen Namen probiere englischen Begriff.
- **USDA-Treffer erscheint nicht:** Warte kurz auf Sensoraktualisierung,
  kontrolliere, dass Suchtext unverändert ist, oder suche erneut.
- **Kalender ist leer:** Kontrolliere Entity `calendar.weekly_meal_planner`
  und erstelle Wochenplan mit **Woche automatisch planen**.
- **Kalorien oder Makros fehlen:** Prüfe Attribut `missing_nutrition` am
  Kaloriensensor. Gewichtseinheit und USDA-Treffer für betroffene Zutaten
  kontrollieren.
- **Kalender- oder Sensor-Entity fehlt:** Öffne **Einstellungen > Geräte &
  Dienste > Weekly Meal Planner** und kontrolliere, ob Integration geladen ist.
  Bei neuen Installationen kann Home-Assistant-Neustart helfen.
