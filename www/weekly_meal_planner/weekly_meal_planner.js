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

  getCardSize() {
    return 4;
  }

  render() {
    this.innerHTML = `
      <style>
        .meal-form { display: grid; gap: 8px; }
        .ingredient-row { display: flex; gap: 8px; margin-bottom: 8px; }
        .ingredient-row input, .ingredient-row select { min-width: 0; flex: 1; }
        .meal-planner-status { min-height: 1.5em; }
      </style>

      <ha-card header="Wochenplaner">
        <div class="card-content">
          <div class="meal-form">
            <h3>Neues Gericht</h3>
            <input id="meal_name" placeholder="Gerichtname" maxlength="100" required>
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

      row.append(name, amount, unit);
      container.appendChild(row);
    };

    this.querySelector("#save_meal").onclick = async () => {
      const name = this.querySelector("#meal_name").value.trim();
      const mealType = this.querySelector("#meal_type").value;
      const ingredients = {};

      for (const row of container.querySelectorAll(".ingredient-row")) {
        const item = row.querySelector('input[aria-label="Zutat"]').value.trim();
        const amount = Number(row.querySelector('input[aria-label="Menge"]').value);
        const unit = row.querySelector("select").value;
        if (!item || !Number.isFinite(amount) || amount <= 0) {
          setStatus("Bitte Gericht und gültige Zutatenmengen eingeben.", true);
          return;
        }
        if (Object.hasOwn(ingredients, item)) {
          setStatus(`Zutat "${item}" ist doppelt. Bitte Mengen zusammenfassen.`, true);
          return;
        }
        ingredients[item] = { amount, unit };
      }

      if (!name || Object.keys(ingredients).length === 0) {
        setStatus("Bitte Gericht und mindestens eine Zutat eingeben.", true);
        return;
      }

      try {
        await this._hass.callService("weekly_meal_planner", "add_meal", {
          name,
          meal_type: mealType,
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
