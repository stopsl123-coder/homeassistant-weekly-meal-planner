class WeeklyMealPlannerCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this.subscribeToNutritionSearchUpdates().catch((error) => {
      console.error("Unable to subscribe to USDA search updates", error);
    });
    if (!this.rendered) {
      this.render();
      this.rendered = true;
    }
    this.updateDashboard();
    this.updateNutritionSearchResults();
  }

  async subscribeToNutritionSearchUpdates() {
    if (typeof this._nutritionSearchSubscription === "function") return;
    if (this._nutritionSearchSubscription) {
      await this._nutritionSearchSubscription;
      return;
    }
    if (!this._hass?.connection) return;

    const generation = this._nutritionSearchGeneration || 0;
    this._nutritionSearchSubscription = this._hass.connection
      .subscribeEvents(
        (event) => {
          if (
            event.data.entity_id === "sensor.weekly_meal_planner_shopping_list"
          ) {
            this.updateNutritionSearchResults(
              event.data.new_state?.attributes.latest_nutrition_search,
            );
          }
        },
        "state_changed",
      )
      .then((unsubscribe) => {
        if (generation !== (this._nutritionSearchGeneration || 0)) {
          unsubscribe();
          return;
        }
        this._nutritionSearchSubscription = unsubscribe;
      })
      .catch((error) => {
        if (generation === (this._nutritionSearchGeneration || 0)) {
          this._nutritionSearchSubscription = undefined;
        }
        throw error;
      });
    await this._nutritionSearchSubscription;
  }

  disconnectedCallback() {
    this._nutritionSearchGeneration =
      (this._nutritionSearchGeneration || 0) + 1;
    if (typeof this._nutritionSearchSubscription === "function") {
      this._nutritionSearchSubscription();
    }
    this._nutritionSearchSubscription = undefined;
  }

  updateDashboard() {
    const state = this._hass?.states["sensor.weekly_meal_planner_calories"];
    const plan = state?.attributes.plan || {};
    const container = this.querySelector("#week_plan");
    if (!container) return;

    container.replaceChildren();
    const entries = Object.entries(plan).sort(([first], [second]) =>
      first.localeCompare(second),
    );
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.textContent = "Noch kein Wochenplan. Mit „Woche automatisch planen“ starten.";
      container.appendChild(empty);
      return;
    }

    for (const [day, meals] of entries) {
      const section = document.createElement("section");
      section.className = "week-day";
      const heading = document.createElement("h4");
      heading.textContent = new Intl.DateTimeFormat("de-DE", {
        weekday: "long",
        day: "numeric",
        month: "short",
      }).format(new Date(`${day}T12:00:00`));
      section.appendChild(heading);
      for (const [mealType, mealName] of Object.entries(meals)) {
        const line = document.createElement("div");
        const label = {
          breakfast: "Frühstück",
          lunch: "Mittagessen",
          dinner: "Abendessen",
        }[mealType] || mealType;
        line.textContent = `${label}: ${mealName}`;
        section.appendChild(line);
      }
      container.appendChild(section);
    }
  }

  updateNutritionSearchResults(search) {
    search ??=
      this._hass?.states["sensor.weekly_meal_planner_shopping_list"]
        ?.attributes.latest_nutrition_search;
    if (!search?.query || !Array.isArray(search.results)) return;

    for (const row of this.querySelectorAll(".ingredient-row")) {
      const input = row.querySelector('input[aria-label="Zutat"]');
      const select = row.querySelector(".usda-match");
      if (input.value.trim().toLocaleLowerCase() !== search.query.toLocaleLowerCase()) {
        select.replaceChildren();
        select.value = "";
        select.hidden = true;
        continue;
      }
      select.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Treffer auswählen";
      select.appendChild(placeholder);
      for (const result of search.results) {
        const option = document.createElement("option");
        option.value = String(result.fdc_id);
        option.textContent = `${result.description} · ${Math.round(result.nutrition.calories)} kcal/100 g`;
        select.appendChild(option);
      }
      select.hidden = search.results.length === 0;
      if (search.results.length === 1) {
        select.value = String(search.results[0].fdc_id);
      }
    }
  }

  getCardSize() {
    return 4;
  }

  render() {
    this.innerHTML = `
      <style>
        .meal-form { display: grid; gap: 8px; }
        .ingredient-row { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 8px; margin-bottom: 8px; }
        .ingredient-row input, .ingredient-row select { min-width: 0; }
        .ingredient-row button, .ingredient-row .usda-match { grid-column: 1 / -1; }
        .week-plan { display: grid; gap: 8px; margin-bottom: 16px; }
        .week-day { padding: 8px; border: 1px solid var(--divider-color); border-radius: 6px; }
        .week-day h4 { margin: 0 0 4px; }
        .meal-planner-status { min-height: 1.5em; }
      </style>

      <ha-card header="Wochenplaner">
        <div class="card-content">
          <h3>Wochenübersicht</h3>
          <div id="week_plan" class="week-plan"></div>
          <div class="meal-form">
            <h3>Neues Gericht</h3>
            <input id="meal_name" placeholder="Gerichtname" maxlength="100" required>
            <label for="servings">Portionen pro Rezept</label>
            <input id="servings" type="number" min="1" max="100" value="2" required>
            <select id="meal_type" aria-label="Mahlzeit">
              <option value="lunch">Mittagessen</option>
              <option value="dinner">Abendessen</option>
              <option value="breakfast">Frühstück</option>
            </select>
            <div id="ingredients_container"></div>
            <button id="add_ingredient" type="button">Zutat hinzufügen</button>
            <button id="save_meal" type="button">Gericht speichern</button>
          </div>
          <p id="status" class="meal-planner-status" role="status" aria-live="polite"></p>
          <button id="auto_plan" type="button">Woche automatisch planen</button>
          <button id="regen_list" type="button">Einkaufsliste aktualisieren</button>
        </div>
      </ha-card>
    `;

    const container = this.querySelector("#ingredients_container");
    const status = this.querySelector("#status");
    const setStatus = (message, isError = false) => {
      status.textContent = message;
      status.setAttribute("aria-invalid", String(isError));
    };

    this.querySelector("#add_ingredient").onclick = () => {
      const row = document.createElement("div");
      row.className = "ingredient-row";

      const name = document.createElement("input");
      name.placeholder = "Zutat";
      name.setAttribute("aria-label", "Zutat");
      name.maxLength = 100;

      const amount = document.createElement("input");
      amount.type = "number";
      amount.min = "0.001";
      amount.step = "any";
      amount.placeholder = "Menge";
      amount.setAttribute("aria-label", "Menge");

      const unit = document.createElement("select");
      unit.setAttribute("aria-label", "Einheit");
      for (const value of ["g", "kg", "mg", "ml", "l", "Stück"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        unit.appendChild(option);
      }

      const search = document.createElement("button");
      search.type = "button";
      search.textContent = "USDA-Treffer suchen";

      const matches = document.createElement("select");
      matches.className = "usda-match";
      matches.setAttribute("aria-label", "USDA-Treffer");
      matches.hidden = true;
      name.addEventListener("input", () => {
        matches.replaceChildren();
        matches.value = "";
        matches.hidden = true;
      });

      search.onclick = async () => {
        const query = name.value.trim();
        if (!query) {
          setStatus("Bitte zuerst Zutatennamen eingeben.", true);
          return;
        }
        try {
          await this.subscribeToNutritionSearchUpdates();
          await this._hass.callService(
            "weekly_meal_planner",
            "search_ingredient",
            { query },
          );
          this.updateNutritionSearchResults();
          setStatus("USDA-Treffer geladen. Passenden Eintrag auswählen.");
        } catch (error) {
          setStatus(error.message || "USDA-Suche fehlgeschlagen.", true);
        }
      };

      row.append(name, amount, unit, search, matches);
      container.appendChild(row);
    };

    this.querySelector("#save_meal").onclick = async () => {
      const name = this.querySelector("#meal_name").value.trim();
      const mealType = this.querySelector("#meal_type").value;
      const servings = Number(this.querySelector("#servings").value);
      const ingredients = {};

      if (!Number.isInteger(servings) || servings < 1 || servings > 100) {
        setStatus("Bitte gültige Portionenzahl zwischen 1 und 100 eingeben.", true);
        return;
      }

      for (const row of container.querySelectorAll(".ingredient-row")) {
        const item = row.querySelector('input[aria-label="Zutat"]').value.trim();
        const amount = Number(row.querySelector('input[aria-label="Menge"]').value);
        const unit = row.querySelector("select").value;
        const selectedMatch = row.querySelector(".usda-match");
        if (!item || !Number.isFinite(amount) || amount <= 0) {
          setStatus("Bitte Gericht und gültige Zutatenmengen eingeben.", true);
          return;
        }
        if (Object.hasOwn(ingredients, item)) {
          setStatus(`Zutat "${item}" ist doppelt. Bitte Mengen zusammenfassen.`, true);
          return;
        }
        if (!selectedMatch.value) {
          setStatus(`Bitte für „${item}“ USDA-Treffer suchen und auswählen.`, true);
          return;
        }
        ingredients[item] = {
          amount,
          unit,
          fdc_id: Number(selectedMatch.value),
        };
      }

      if (!name || Object.keys(ingredients).length === 0) {
        setStatus("Bitte Gericht und mindestens eine Zutat eingeben.", true);
        return;
      }

      try {
        await this._hass.callService("weekly_meal_planner", "add_meal", {
          name,
          meal_type: mealType,
          servings,
          ingredients,
        });
        setStatus("Gericht gespeichert und Nährwerte ergänzt.");
      } catch (error) {
        setStatus(error.message || "Gericht konnte nicht gespeichert werden.", true);
      }
    };

    this.querySelector("#auto_plan").onclick = async () => {
      try {
        await this._hass.callService(
          "weekly_meal_planner",
          "generate_week_plan",
          {},
        );
        setStatus("Wochenplan wurde aktualisiert.");
      } catch (error) {
        setStatus(error.message || "Wochenplan konnte nicht erstellt werden.", true);
      }
    };

    this.querySelector("#regen_list").onclick = async () => {
      try {
        await this._hass.callService(
          "weekly_meal_planner",
          "generate_shopping_list",
          {},
        );
        setStatus("Einkaufsliste wurde aktualisiert.");
      } catch (error) {
        setStatus(error.message || "Einkaufsliste konnte nicht aktualisiert werden.", true);
      }
    };
  }
}

if (!customElements.get("weekly-meal-planner-card")) {
  customElements.define("weekly-meal-planner-card", WeeklyMealPlannerCard);
}
