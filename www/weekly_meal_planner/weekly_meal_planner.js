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

  setPlanStatus(message, isError = false) {
    const status = this.querySelector("#status");
    if (status) {
      status.textContent = message;
      status.style.color = isError ? "var(--error-color)" : "";
    }
    const mealDialog = this.querySelector("#meal_dialog");
    const recipeDialog = this.querySelector("#recipe_dialog");
    const dialogStatus = mealDialog.open
      ? this.querySelector("#meal_dialog_status")
      : recipeDialog.open
        ? this.querySelector("#recipe_dialog_status")
        : undefined;
    if (dialogStatus) {
      dialogStatus.textContent = message;
      dialogStatus.style.color = isError ? "var(--error-color)" : "";
    }
  }

  openMealDialog(day, mealType, mealName, recipes) {
    const labels = {
      breakfast: "Frühstück",
      lunch: "Mittagessen",
      dinner: "Abendessen",
    };
    this._selectedMealSlot = { day, mealType };
    const dialog = this.querySelector("#meal_dialog");
    const select = this.querySelector("#meal_choice");
    const save = this.querySelector("#save_planned_meal");
    const deleteButton = this.querySelector("#delete_meal");
    const empty = this.querySelector("#meal_choice_empty");
    this.querySelector("#meal_dialog_title").textContent =
      `${labels[mealType]} · ${new Intl.DateTimeFormat("de-DE", {
        weekday: "long",
        day: "numeric",
        month: "long",
      }).format(new Date(`${day}T12:00:00`))}`;
    select.replaceChildren();
    const candidates = recipes.filter((item) => item.meal_type === mealType);
    for (const recipe of candidates) {
      const option = document.createElement("option");
      option.value = recipe.name;
      option.textContent =
        recipe.calories == null
          ? `${recipe.name} · Kalorien unbekannt`
          : `${recipe.name} · ${Math.round(recipe.calories)} kcal pro Portion`;
      select.appendChild(option);
    }
    if (!candidates.length && !mealName) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Keine gespeicherten Gerichte dieser Kategorie";
      select.appendChild(option);
    }
    if (mealName && !recipes.some((recipe) => recipe.name === mealName)) {
      const option = document.createElement("option");
      option.value = mealName;
      option.textContent = `${mealName} · nicht mehr gespeichert`;
      select.appendChild(option);
    }
    select.value = mealName || select.options[0]?.value || "";
    save.disabled = !select.value;
    deleteButton.disabled = !recipes.some((recipe) => recipe.name === select.value);
    empty.hidden = candidates.length > 0;
    empty.textContent = `Noch keine gespeicherten Gerichte für ${labels[mealType]}.`;
    this.querySelector("#meal_dialog_status").textContent = "";
    select.onchange = () => {
      save.disabled = !select.value;
      deleteButton.disabled = !recipes.some(
        (recipe) => recipe.name === select.value,
      );
    };
    dialog.showModal();
  }

  async savePlannedMeal(mealName) {
    const slot = this._selectedMealSlot;
    if (!slot) return;
    if (!mealName) {
      this.setPlanStatus("Bitte zuerst ein Gericht auswählen.", true);
      return;
    }
    const save = this.querySelector("#save_planned_meal");
    save.disabled = true;
    try {
      await this._hass.callService("weekly_meal_planner", "set_planned_meal", {
        day: slot.day,
        meal_type: slot.mealType,
        meal_name: mealName,
      });
      this.querySelector("#meal_dialog").close();
      this.setPlanStatus("Gericht wurde im Wochenplan gespeichert.");
    } catch (error) {
      this.setPlanStatus(
        error.message || "Gericht konnte nicht gespeichert werden.",
        true,
      );
    } finally {
      save.disabled = false;
    }
  }

  async deleteMeal(mealName) {
    if (!mealName) return;
    if (
      !window.confirm(
        `„${mealName}“ wirklich löschen? Es wird auch aus allen Wochenplan-Tagen entfernt.`,
      )
    ) {
      return;
    }

    const button = this.querySelector("#delete_meal");
    button.disabled = true;
    try {
      await this._hass.callService("weekly_meal_planner", "delete_meal", {
        name: mealName,
      });
      this.querySelector("#meal_dialog").close();
      this.setPlanStatus(`„${mealName}“ wurde gelöscht.`);
    } catch (error) {
      this.setPlanStatus(error.message || "Gericht konnte nicht gelöscht werden.", true);
    } finally {
      button.disabled = false;
    }
  }

  openRecipeDialog(mealType, day = undefined) {
    const dialog = this.querySelector("#recipe_dialog");
    const typeSelect = this.querySelector("#meal_type");
    this.querySelector("#meal_dialog").close();
    typeSelect.value = mealType || "lunch";
    typeSelect.disabled = Boolean(day);
    this._pendingMealSlot = day ? { day, mealType } : undefined;
    dialog.showModal();
    this.querySelector("#meal_name").focus();
  }

  updateDashboard() {
    const state = this._hass?.states["sensor.weekly_meal_planner_calories"];
    const plan = state?.attributes.plan || {};
    const recipes = state?.attributes.meals || [];
    const dailyCalories = state?.attributes.per_day || {};
    const days = state?.attributes.week_days || Object.keys(plan);
    const container = this.querySelector("#week_plan");
    if (!container) return;

    container.replaceChildren();
    if (!days.length) {
      const empty = document.createElement("p");
      empty.textContent = "Wochenplan wird geladen.";
      container.appendChild(empty);
      return;
    }

    for (const day of days) {
      const plannedMeals = plan[day] || {};
      const section = document.createElement("section");
      section.className = "week-day";
      const heading = document.createElement("h4");
      heading.textContent = new Intl.DateTimeFormat("de-DE", {
        weekday: "long",
        day: "numeric",
        month: "short",
      }).format(new Date(`${day}T12:00:00`));
      section.appendChild(heading);
      const dailyTotal = document.createElement("small");
      dailyTotal.className = "day-calories";
      const calories = dailyCalories[day];
      dailyTotal.textContent =
        calories == null
          ? Object.keys(plannedMeals).length
            ? "Tagesgesamt: unvollständig"
            : "0 kcal gesamt"
          : `${Math.round(calories)} kcal gesamt`;
      section.appendChild(dailyTotal);
      for (const mealType of ["breakfast", "lunch", "dinner"]) {
        const recipeName = plannedMeals[mealType];
        const recipe = recipes.find((item) => item.name === recipeName);
        const tile = document.createElement("button");
        tile.type = "button";
        tile.className = recipeName ? "meal-tile is-planned" : "meal-tile is-empty";
        tile.setAttribute(
          "aria-label",
          `${{ breakfast: "Frühstück", lunch: "Mittagessen", dinner: "Abendessen" }[mealType]} am ${day}: ${recipeName || "Gericht auswählen"}`,
        );
        const typeLabel = document.createElement("strong");
        typeLabel.textContent = {
          breakfast: "Frühstück",
          lunch: "Mittagessen",
          dinner: "Abendessen",
        }[mealType];
        const title = document.createElement("span");
        title.textContent = recipeName || "+ Gericht auswählen";
        tile.append(typeLabel, title);
        if (recipeName) {
          const calories = document.createElement("small");
          calories.textContent =
            recipe?.calories == null
              ? "Kalorien unbekannt"
              : `${Math.round(recipe.calories)} kcal pro Portion`;
          tile.appendChild(calories);
        }
        tile.addEventListener("click", () =>
          this.openMealDialog(day, mealType, recipeName, recipes),
        );
        section.appendChild(tile);
      }
      container.appendChild(section);
    }
  }

  updateNutritionSearchResults(search) {
    const latestSearch =
      search ??
      this._hass?.states["sensor.weekly_meal_planner_shopping_list"]
        ?.attributes.latest_nutrition_search;

    for (const row of this.querySelectorAll(".ingredient-row")) {
      const input = row.querySelector('input[aria-label="Zutat"]');
      const query = input.value.trim().toLocaleLowerCase();
      const rowSearch =
        row._nutritionSearch?.query?.toLocaleLowerCase() === query
          ? row._nutritionSearch
          : latestSearch?.query?.toLocaleLowerCase() === query
            ? latestSearch
            : undefined;

      if (!rowSearch || !Array.isArray(rowSearch.results)) {
        if (row._nutritionSearch) {
          row._nutritionSearch = undefined;
          const select = row.querySelector(".usda-match");
          select.replaceChildren();
          select.value = "";
          select.hidden = true;
        }
        continue;
      }

      if (search && search.query?.toLocaleLowerCase() === query) {
        row._nutritionSearch = search;
      } else if (!row._nutritionSearch) {
        row._nutritionSearch = rowSearch;
      }
      this.renderNutritionMatches(row, row._nutritionSearch);
    }
  }

  renderNutritionMatches(row, search) {
    const select = row.querySelector(".usda-match");
    const unit = row.querySelector('select[aria-label="Einheit"]').value;
    const weight = Number(
      row.querySelector('input[aria-label="Gewicht pro Stück in Gramm"]').value,
    );
    const selectedValue = select.value;
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Treffer auswählen";
    select.appendChild(placeholder);
    for (const result of search.results) {
      const option = document.createElement("option");
      option.value = String(result.fdc_id);
      const caloriesPer100g = Number(result.nutrition.calories);
      const nutritionLabel =
        unit === "Stück" && Number.isFinite(weight) && weight > 0
          ? `${Math.round((caloriesPer100g * weight) / 100)} kcal je Stück (${weight} g)`
          : `${Math.round(caloriesPer100g)} kcal je 100 g`;
      option.textContent = `${search.query} · USDA: ${result.description} · ${nutritionLabel}`;
      select.appendChild(option);
    }
    select.hidden = search.results.length === 0;
    if (search.results.some((result) => String(result.fdc_id) === selectedValue)) {
      select.value = selectedValue;
    } else if (search.results.length === 1) {
      select.value = String(search.results[0].fdc_id);
    }
  }

  getCardSize() {
    return 4;
  }

  render() {
    this.innerHTML = `
      <style>
        weekly-meal-planner-card { display: block; }
        ha-card.planner-card {
          overflow: hidden;
          border: 1px solid var(--divider-color);
          border-radius: 24px;
          background: var(--ha-card-background, var(--card-background-color));
          box-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
        }
        .planner-card > .card-content { padding: clamp(18px, 3vw, 30px); }
        .planner-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
        .planner-eyebrow { margin: 0 0 6px; color: var(--primary-color); font-size: .72rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
        .planner-title { margin: 0; font-size: clamp(1.45rem, 2vw, 2rem); font-weight: 750; letter-spacing: -.035em; line-height: 1.15; }
        .planner-description { margin: 8px 0 0; color: var(--secondary-text-color); font-size: .92rem; }
        .week-count { flex: 0 0 auto; padding: 8px 12px; border: 1px solid var(--divider-color); border-radius: 999px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: .8rem; font-weight: 700; }
        .week-plan-viewport { overflow-x: auto; padding: 2px 2px 10px; scrollbar-width: thin; }
        .week-plan-viewport:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .week-plan { display: grid; grid-template-columns: repeat(7, minmax(112px, 1fr)); min-width: 840px; gap: 10px; margin-bottom: 14px; }
        .week-day { display: flex; min-width: 0; flex-direction: column; padding: 10px; border: 1px solid var(--divider-color); border-radius: 18px; background: var(--secondary-background-color); overflow-wrap: anywhere; }
        .week-day h4 { display: flex; min-height: 2.5em; align-items: center; margin: 0 0 4px; padding: 2px 2px 10px; border-bottom: 1px solid var(--divider-color); font-size: .86rem; font-weight: 750; line-height: 1.25; text-transform: capitalize; }
        .day-calories { width: fit-content; margin: 2px 0 3px; padding: 4px 7px; border-radius: 999px; background: var(--primary-color); color: var(--text-primary-color, #fff); font-size: .64rem; font-weight: 750; }
        .meal-tile { display: grid; gap: 7px; width: 100%; min-height: 88px; margin-top: 8px; padding: 10px 9px; appearance: none; border: 1px solid var(--divider-color); border-radius: 13px; background: var(--ha-card-background, var(--card-background-color)); color: var(--primary-text-color); text-align: left; white-space: normal; overflow-wrap: anywhere; cursor: pointer; transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
        .meal-tile:hover { transform: translateY(-2px); border-color: var(--primary-color); box-shadow: 0 7px 18px rgba(0, 0, 0, .1); }
        .meal-tile:focus-visible, .planner-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .meal-tile strong { color: var(--secondary-text-color); font-size: .65rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
        .meal-tile span { font-size: .82rem; font-weight: 650; line-height: 1.35; }
        .meal-tile small { width: fit-content; padding: 3px 7px; border-radius: 999px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: .68rem; }
        .meal-tile.is-empty { align-content: center; border-style: dashed; background: transparent; }
        .meal-tile.is-empty span { color: var(--secondary-text-color); font-weight: 550; }
        .planner-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 18px; }
        .planner-button { min-height: 42px; padding: 9px 16px; border: 1px solid var(--divider-color); border-radius: 12px; background: var(--secondary-background-color); color: var(--primary-text-color); font: inherit; font-size: .86rem; font-weight: 700; cursor: pointer; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
        .planner-button:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(0, 0, 0, .12); }
        .planner-button.primary { border-color: var(--primary-color); background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .meal-planner-status { min-height: 1.5em; margin: 14px 0 0; color: var(--secondary-text-color); font-size: .86rem; }
        .meal-form { display: grid; gap: 12px; }
        .meal-form h3, weekly-meal-planner-card #meal_dialog h3 { margin: 0 0 6px; font-size: 1.35rem; letter-spacing: -.02em; }
        .ingredient-row { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 8px; margin-bottom: 10px; padding: 12px; border: 1px solid var(--divider-color); border-radius: 14px; background: var(--secondary-background-color); }
        .ingredient-row input, .ingredient-row select, weekly-meal-planner-card dialog input, weekly-meal-planner-card dialog select { box-sizing: border-box; min-width: 0; min-height: 42px; padding: 9px 11px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--ha-card-background, var(--card-background-color)); color: var(--primary-text-color); font: inherit; }
        .ingredient-row button, .ingredient-row .piece-weight, .ingredient-row .usda-match { grid-column: 1 / -1; }
        .ingredient-row button, #add_ingredient, #save_meal, weekly-meal-planner-card .dialog-actions button { min-height: 40px; padding: 8px 13px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--secondary-background-color); color: var(--primary-text-color); font: inherit; font-weight: 650; cursor: pointer; }
        #save_meal, #save_planned_meal { border-color: var(--primary-color); background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .piece-weight { display: none; gap: 6px; color: var(--secondary-text-color); font-size: .82rem; }
        .piece-weight.visible { display: grid; }
        weekly-meal-planner-card dialog { box-sizing: border-box; width: min(560px, calc(100vw - 32px)); max-height: 85vh; padding: 24px; overflow: auto; color: var(--primary-text-color); background: var(--ha-card-background, var(--card-background-color)); border: 1px solid var(--divider-color); border-radius: 22px; box-shadow: 0 24px 80px rgba(0, 0, 0, .24); }
        weekly-meal-planner-card dialog::backdrop { background: rgba(12, 18, 28, .58); backdrop-filter: blur(5px); }
        #meal_dialog label { display: block; margin: 12px 0 6px; color: var(--secondary-text-color); font-size: .82rem; font-weight: 700; }
        #meal_dialog select { width: 100%; }
        weekly-meal-planner-card .dialog-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 18px; }
        #delete_meal { margin-right: auto; border-color: var(--error-color); color: var(--error-color); }
        .recipe-dialog-content { padding: 2px; }
        weekly-meal-planner-card #recipe_dialog .meal-form > p { color: var(--secondary-text-color); font-size: .84rem; line-height: 1.5; }
        #meal_choice_empty { padding: 12px; border-radius: 12px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
        @media (max-width: 600px) {
          .planner-header { gap: 10px; }
          .week-count { padding: 6px 9px; font-size: .72rem; }
          .planner-actions { align-items: stretch; }
          .planner-actions button { flex: 1 1 100%; }
          weekly-meal-planner-card dialog { padding: 18px; }
        }
        @media (prefers-reduced-motion: reduce) {
          .meal-tile, .planner-button { transition: none; }
          .meal-tile:hover, .planner-button:hover { transform: none; }
        }
      </style>

      <ha-card class="planner-card">
        <div class="card-content">
          <header class="planner-header">
            <div>
              <p class="planner-eyebrow">Dein Wochenplan</p>
              <h2 class="planner-title">Deine Woche</h2>
              <p class="planner-description">Frühstück, Mittag- und Abendessen auf einen Blick.</p>
            </div>
            <span class="week-count">7 Tage</span>
          </header>
          <div class="week-plan-viewport" role="region" aria-label="Wochenübersicht" tabindex="0">
            <div id="week_plan" class="week-plan"></div>
          </div>
          <div class="planner-actions">
            <button id="new_meal" class="planner-button" type="button">Neues Gericht</button>
            <button id="auto_plan" class="planner-button primary" type="button">Woche automatisch planen</button>
            <button id="regen_list" class="planner-button" type="button">Einkaufsliste aktualisieren</button>
          </div>
          <p id="status" class="meal-planner-status" role="status" aria-live="polite"></p>
        </div>
        <dialog id="meal_dialog">
          <h3 id="meal_dialog_title">Gericht auswählen</h3>
          <label for="meal_choice">Gespeichertes Gericht</label>
          <select id="meal_choice"></select>
          <p id="meal_choice_empty" hidden></p>
          <p id="meal_dialog_status" role="status" aria-live="polite"></p>
          <div class="dialog-actions">
            <button id="delete_meal" type="button">Gericht löschen</button>
            <button id="new_meal_for_slot" type="button">Neues Gericht anlegen</button>
            <button id="save_planned_meal" type="button">In Wochenplan übernehmen</button>
            <button id="close_meal_dialog" type="button">Abbrechen</button>
          </div>
        </dialog>
        <dialog id="recipe_dialog">
          <div class="recipe-dialog-content">
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
            <p>USDA-Treffernamen können Englisch sein. Nährwerte gelten je 100 g; für „Stück“ Gewicht pro Stück angeben.</p>
            <p id="recipe_dialog_status" role="status" aria-live="polite"></p>
            <button id="add_ingredient" type="button">Zutat hinzufügen</button>
            <button id="save_meal" type="button">Gericht speichern</button>
          </div>
            <div class="dialog-actions">
              <button id="close_recipe_dialog" type="button">Schließen</button>
            </div>
          </div>
        </dialog>
      </ha-card>
    `;

    const container = this.querySelector("#ingredients_container");
    const status = this.querySelector("#status");
    const setStatus = (message, isError = false) => {
      status.textContent = message;
      status.setAttribute("aria-invalid", String(isError));
      const dialogStatus = this.querySelector("#recipe_dialog_status");
      if (this.querySelector("#recipe_dialog").open) {
        dialogStatus.textContent = message;
        dialogStatus.style.color = isError ? "var(--error-color)" : "";
      }
    };

    this.querySelector("#new_meal").onclick = () =>
      this.openRecipeDialog(this.querySelector("#meal_type").value);
    this.querySelector("#new_meal_for_slot").onclick = () => {
      const slot = this._selectedMealSlot;
      this.openRecipeDialog(slot?.mealType, slot?.day);
    };
    this.querySelector("#close_meal_dialog").onclick = () =>
      this.querySelector("#meal_dialog").close();
    this.querySelector("#save_planned_meal").onclick = () =>
      this.savePlannedMeal(this.querySelector("#meal_choice").value);
    this.querySelector("#delete_meal").onclick = () =>
      this.deleteMeal(this.querySelector("#meal_choice").value);
    this.querySelector("#close_recipe_dialog").onclick = () =>
      this.querySelector("#recipe_dialog").close();
    this.querySelector("#recipe_dialog").addEventListener("close", () => {
      this._pendingMealSlot = undefined;
      this.querySelector("#meal_type").disabled = false;
    });

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

      const pieceWeight = document.createElement("label");
      pieceWeight.className = "piece-weight";
      pieceWeight.textContent = "Gewicht pro Stück (g)";
      const weightPerUnit = document.createElement("input");
      weightPerUnit.type = "number";
      weightPerUnit.min = "0.001";
      weightPerUnit.step = "any";
      weightPerUnit.placeholder = "z. B. 60";
      weightPerUnit.setAttribute(
        "aria-label",
        "Gewicht pro Stück in Gramm",
      );
      pieceWeight.appendChild(weightPerUnit);

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
        row._nutritionSearch = undefined;
      });
      unit.addEventListener("change", () => {
        const isPiece = unit.value === "Stück";
        pieceWeight.classList.toggle("visible", isPiece);
        weightPerUnit.required = isPiece;
        if (row._nutritionSearch) {
          this.renderNutritionMatches(row, row._nutritionSearch);
        }
      });
      weightPerUnit.addEventListener("input", () => {
        if (row._nutritionSearch) {
          this.renderNutritionMatches(row, row._nutritionSearch);
        }
      });

      search.onclick = async () => {
        const query = name.value.trim();
        if (!query) {
          setStatus("Bitte zuerst Zutatennamen eingeben.", true);
          return;
        }
        try {
          const serviceResult = await this._hass.callService(
            "weekly_meal_planner",
            "search_ingredient",
            { query },
            undefined,
            false,
            true,
          );
          const search = serviceResult?.response;
          if (
            search?.query?.toLocaleLowerCase() === query.toLocaleLowerCase() &&
            Array.isArray(search.results)
          ) {
            this.updateNutritionSearchResults(search);
          }
          const matches = row.querySelector(".usda-match");
          if (!matches || matches.hidden || !matches.options.length) {
            throw new Error(
              "USDA-Suche lieferte Treffer, Auswahl konnte nicht angezeigt werden.",
            );
          }
          setStatus("USDA-Treffer geladen. Passenden Eintrag auswählen.");
        } catch (error) {
          setStatus(error.message || "USDA-Suche fehlgeschlagen.", true);
        }
      };

      row.append(name, amount, unit, pieceWeight, search, matches);
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
        const weightPerUnit = row.querySelector(
          'input[aria-label="Gewicht pro Stück in Gramm"]',
        );
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
        if (
          unit === "Stück" &&
          (!Number.isFinite(Number(weightPerUnit.value)) ||
            Number(weightPerUnit.value) <= 0)
        ) {
          setStatus(`Bitte Gewicht pro Stück für „${item}“ in Gramm eingeben.`, true);
          return;
        }
        ingredients[item] = {
          amount,
          unit,
          fdc_id: Number(selectedMatch.value),
          ...(unit === "Stück"
            ? { weight_per_unit_g: Number(weightPerUnit.value) }
            : {}),
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
      } catch (error) {
        setStatus(error.message || "Gericht konnte nicht gespeichert werden.", true);
        return;
      }

      const slot = this._pendingMealSlot;
      if (slot) {
        try {
          await this._hass.callService(
            "weekly_meal_planner",
            "set_planned_meal",
            { day: slot.day, meal_type: slot.mealType, meal_name: name },
          );
        } catch (error) {
          setStatus(
            `Gericht gespeichert, aber nicht eingeplant: ${error.message}`,
            true,
          );
          return;
        }
      }
      this._pendingMealSlot = undefined;
      setStatus(
        slot
          ? "Gericht gespeichert und im Wochenplan eingetragen."
          : "Gericht gespeichert und Nährwerte ergänzt.",
      );
      this.querySelector("#recipe_dialog").close();
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
