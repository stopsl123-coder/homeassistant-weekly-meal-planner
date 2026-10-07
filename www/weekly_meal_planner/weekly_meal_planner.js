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
