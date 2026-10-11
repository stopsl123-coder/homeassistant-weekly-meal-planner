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
    if (!this._selectedWeekStart) {
      this._selectedWeekStart = this._currentWeekStart();
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

  _currentWeekStart() {
    const attributes =
      this._hass?.states["sensor.weekly_meal_planner_calories"]?.attributes || {};
    if (attributes.week_start || attributes.week_days?.[0]) {
      return attributes.week_start || attributes.week_days[0];
    }
    const today = new Date();
    today.setDate(today.getDate() - ((today.getDay() + 6) % 7));
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  }

  _addWeek(weekStart, weeks) {
    const date = new Date(`${weekStart}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + weeks * 7);
    return date.toISOString().slice(0, 10);
  }

  async loadWeekData(weekStart = this._selectedWeekStart) {
    this._selectedWeekStart = weekStart;
    this._weekData = undefined;
    this._weekLoadError = false;
    this.updateDashboard();
    try {
      const result = await this._hass.callService(
        "weekly_meal_planner",
        "get_week_data",
        { week_start: weekStart },
        undefined,
        false,
        true,
      );
      this._weekData = result?.response;
      if (!this._weekData) {
        throw new Error("Wochenplan konnte nicht geladen werden.");
      }
      this.updateDashboard();
      return true;
    } catch (error) {
      this._weekLoadError = true;
      this.updateDashboard();
      this.setPlanStatus(error.message || "Wochenplan konnte nicht geladen werden.", true);
      return false;
    }
  }

  async changeWeek(offset) {
    const currentWeek = this._currentWeekStart();
    const nextWeek = this._addWeek(currentWeek, 1);
    const target = this._addWeek(this._selectedWeekStart || currentWeek, offset);
    if (target !== currentWeek && target !== nextWeek) return;
    this._selectedWeekStart = target;
    if (target === currentWeek) {
      this._weekData = undefined;
      this.updateDashboard();
      return;
    }
    await this.loadWeekData(target);
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
    const ingredientsHeading = this.querySelector(
      "#saved_recipe_ingredients_heading",
    );
    const ingredientsList = this.querySelector("#saved_recipe_ingredients");
    const instructions = this.querySelector("#saved_recipe_instructions");
    const sourceLink = this.querySelector("#saved_recipe_source");
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
    const dialogStatus = this.querySelector("#meal_dialog_status");
    dialogStatus.textContent = "";
    let detailsRequest = 0;
    const showRecipeDetails = async () => {
      const request = ++detailsRequest;
      ingredientsHeading.hidden = true;
      ingredientsList.replaceChildren();
      ingredientsList.hidden = true;
      instructions.textContent = "";
      instructions.hidden = true;
      sourceLink.hidden = true;
      const recipe = recipes.find((item) => item.name === select.value);
      if (!recipe) return;
      dialogStatus.textContent = "Rezeptdetails werden geladen.";
      try {
        const result = await this._hass.callService(
          "weekly_meal_planner",
          "get_meal_details",
          { name: recipe.name },
          undefined,
          false,
          true,
        );
        const details = result?.response;
        if (!details) {
          throw new Error("Rezeptdetails konnten nicht geladen werden.");
        }
        if (request !== detailsRequest) return;
        for (const [name, ingredient] of Object.entries(details.ingredients || {})) {
          const item = document.createElement("li");
          const amount = Number(ingredient?.amount);
          const quantity =
            Number.isFinite(amount) && ingredient?.unit
              ? ` · ${amount.toLocaleString("de-DE")} ${ingredient.unit}`
              : "";
          item.textContent = `${name}${quantity}`;
          ingredientsList.appendChild(item);
        }
        ingredientsList.hidden = !ingredientsList.childElementCount;
        ingredientsHeading.hidden = !ingredientsList.childElementCount;
        instructions.textContent = details.instructions || "";
        instructions.hidden = !details.instructions;
        const sourceName = details.source_name;
        const sourceUrl =
          details.source_url ||
          (sourceName.startsWith("Wikibooks")
            ? "https://de.wikibooks.org/wiki/Kochbuch"
            : "");
        sourceLink.hidden = !sourceName && !sourceUrl;
        sourceLink.textContent = sourceName
          ? `Rezeptquelle: ${sourceName}`
          : "Rezeptquelle öffnen";
        if (sourceUrl) {
          sourceLink.href = sourceUrl;
          sourceLink.target = "_blank";
          sourceLink.rel = "noopener noreferrer";
        } else {
          sourceLink.removeAttribute("href");
        }
        dialogStatus.textContent = "";
      } catch (error) {
        if (request !== detailsRequest) return;
        dialogStatus.textContent =
          error.message || "Rezeptdetails konnten nicht geladen werden.";
      }
    };
    showRecipeDetails();
    select.onchange = () => {
      save.disabled = !select.value;
      deleteButton.disabled = !recipes.some(
        (recipe) => recipe.name === select.value,
      );
      showRecipeDetails();
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
      if (mondayOf(slot.day) !== this._currentWeekStart()) {
        await this.loadWeekData(this._selectedWeekStart);
      }
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
      await this.loadWeekData(this._selectedWeekStart);
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
    this.querySelector("#meal_name").value = "";
    this.querySelector("#servings").value = "2";
    this.querySelector("#recipe_instructions").value = "";
    this.querySelector("#recipe_source_url").value = "";
    this.querySelector("#recipe_source_name").value = "";
    this.querySelector("#ingredients_container").replaceChildren();
    this.querySelector("#recipe_search_query").value = "";
    this.querySelector("#recipe_search_results").replaceChildren();
    this.querySelector("#recipe_search_status").textContent = "";
    this.querySelector("#nutrition_source").value = "bls";
    dialog.showModal();
    this.querySelector("#meal_name").focus();
  }

  async searchRecipeCatalog() {
    const query = this.querySelector("#recipe_search_query").value.trim();
    const status = this.querySelector("#recipe_search_status");
    const resultsContainer = this.querySelector("#recipe_search_results");
    resultsContainer.replaceChildren();
    if (!query) {
      status.textContent = "Gerichtname eingeben.";
      return;
    }
    status.textContent = "Das deutsche Wikibooks-Kochbuch wird durchsucht.";
    try {
      const serviceResult = await this._hass.callService(
        "weekly_meal_planner",
        "search_recipe",
        { query },
        undefined,
        false,
        true,
      );
      const recipes = serviceResult?.response?.results;
      if (!Array.isArray(recipes)) {
        throw new Error("Wikibooks lieferte ungültige Suchergebnisse.");
      }
      if (!recipes.length) {
        status.textContent = "Keine passenden Gerichte gefunden.";
        return;
      }
      status.textContent = `${recipes.length} Gerichte gefunden. Gericht zum Übernehmen auswählen.`;
      for (const recipe of recipes) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recipe-search-result";
        button.textContent = [
          recipe.name,
          recipe.area,
          recipe.category,
        ].filter(Boolean).join(" · ");
        button.onclick = () => this.importRecipe(recipe);
        resultsContainer.appendChild(button);
      }
    } catch (error) {
      status.textContent =
        error.message || "Wikibooks-Rezeptsuche fehlgeschlagen.";
    }
  }

  importRecipe(recipe) {
    this.querySelector("#meal_name").value = recipe.name || "";
    this.querySelector("#servings").value = String(
      Math.min(100, Math.max(1, Number(recipe.servings) || 2)),
    );
    this.querySelector("#recipe_instructions").value = recipe.instructions || "";
    this.querySelector("#recipe_source_url").value = recipe.source_url || "";
    this.querySelector("#recipe_source_name").value =
      recipe.source || "Wikibooks Kochbuch";
    if (String(recipe.category || "").toLocaleLowerCase() === "breakfast") {
      this.querySelector("#meal_type").value = "breakfast";
    }
    const ingredientsContainer = this.querySelector("#ingredients_container");
    ingredientsContainer.replaceChildren();
    for (const ingredient of recipe.ingredients || []) {
      this.querySelector("#add_ingredient").click();
      const row = ingredientsContainer.lastElementChild;
      row.querySelector('input[aria-label="Zutat"]').value = ingredient.name;
      const measure = ingredient.measure || "";
      const measureHint = row.querySelector(".recipe-measure-hint");
      measureHint.textContent = measure
        ? `Originalmenge: ${measure} · bitte prüfen`
        : "Menge in g, kg oder ml ergänzen.";
      measureHint.hidden = false;
      const parsedMeasure = parseRecipeMeasure(measure);
      if (parsedMeasure) {
        row.querySelector('input[aria-label="Menge"]').value = parsedMeasure.amount;
        row.querySelector('select[aria-label="Einheit"]').value = parsedMeasure.unit;
      } else {
        row.querySelector('input[aria-label="Menge"]').value = "";
      }
    }
    this.querySelector("#recipe_search_status").textContent =
      "Deutsches Rezept übernommen. Mengen prüfen und für jede Zutat BLS-Nährwerttreffer auswählen.";
    this.querySelector("#recipe_search_results").replaceChildren();
  }

  updateDashboard() {
    const state = this._hass?.states["sensor.weekly_meal_planner_calories"];
    const attributes = state?.attributes || {};
    const currentWeek = this._currentWeekStart();
    const selectedWeek = this._selectedWeekStart || currentWeek;
    const weekData =
      selectedWeek === currentWeek ? attributes : this._weekData || {};
    const plan = weekData.plan || {};
    const recipes = weekData.meals || [];
    const dailyCalories =
      weekData.per_day || weekData.nutrition?.per_day || {};
    const days = weekData.week_days || Object.keys(plan);
    const container = this.querySelector("#week_plan");
    if (!container) return;

    const weekLabel = this.querySelector("#selected_week_label");
    const weekStartDate = new Date(`${selectedWeek}T12:00:00`);
    const weekEndDate = new Date(`${this._addWeek(selectedWeek, 1)}T12:00:00`);
    weekEndDate.setDate(weekEndDate.getDate() - 1);
    const dateFormatter = new Intl.DateTimeFormat("de-DE", {
      day: "numeric",
      month: "short",
    });
    weekLabel.textContent =
      selectedWeek === currentWeek
        ? `Aktuelle Woche · ${dateFormatter.format(weekStartDate)}–${dateFormatter.format(weekEndDate)}`
        : `Nächste Woche · ${dateFormatter.format(weekStartDate)}–${dateFormatter.format(weekEndDate)}`;
    this.querySelector("#previous_week").disabled = selectedWeek === currentWeek;
    this.querySelector("#next_week").disabled =
      selectedWeek === this._addWeek(currentWeek, 1);
    this.querySelector("#auto_plan").textContent =
      selectedWeek === currentWeek
        ? "Diese Woche automatisch planen"
        : "Nächste Woche automatisch planen";

    container.replaceChildren();
    if (selectedWeek !== currentWeek && !this._weekData) {
      const loading = document.createElement("p");
      loading.textContent = this._weekLoadError
        ? "Wochenplan konnte nicht geladen werden."
        : "Wochenplan wird geladen.";
      container.appendChild(loading);
      this.querySelector("#shopping_items").replaceChildren();
      const shoppingEmpty = this.querySelector("#shopping_empty");
      shoppingEmpty.hidden = false;
      shoppingEmpty.textContent = this._weekLoadError
        ? "Einkaufsliste konnte nicht geladen werden."
        : "Einkaufsliste wird geladen.";
      return;
    }
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
    const shoppingList =
      selectedWeek === currentWeek
        ? this._hass?.states["sensor.weekly_meal_planner_shopping_list"]?.attributes.items
        : weekData.shopping_list;
    this.renderShoppingList(shoppingList || {});
  }

  renderShoppingList(items) {
    const list = this.querySelector("#shopping_items");
    const empty = this.querySelector("#shopping_empty");
    list.replaceChildren();
    const entries = Object.entries(items || {}).sort(([left], [right]) =>
      left.localeCompare(right, "de"),
    );
    empty.hidden = entries.length > 0;
    empty.textContent = entries.length
      ? ""
      : "Für diese Woche sind noch keine Gerichte eingeplant.";
    for (const [name, details] of entries) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = name;
      const amount = document.createElement("strong");
      amount.textContent = `${Number(details.amount).toLocaleString("de-DE")} ${details.unit}`;
      item.append(label, amount);
      list.appendChild(item);
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
      const source = this.querySelector("#nutrition_source").value;
      const rowSearch =
        row._nutritionSearch?.query?.toLocaleLowerCase() === query &&
        row._nutritionSearch.source === source
          ? row._nutritionSearch
          : latestSearch?.query?.toLocaleLowerCase() === query &&
              (latestSearch.source || "usda") === source
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
      const identifier = result.bls_code ?? result.fdc_id;
      option.value = String(identifier);
      const caloriesPer100g = Number(result.nutrition.calories);
      const nutritionLabel =
        unit === "Stück" && Number.isFinite(weight) && weight > 0
          ? `${Math.round((caloriesPer100g * weight) / 100)} kcal je Stück (${weight} g)`
          : `${Math.round(caloriesPer100g)} kcal je 100 g`;
      const sourceLabel = result.bls_code ? "BLS" : "USDA";
      const label = result.description_en
        ? `${result.description} / ${result.description_en}`
        : result.description;
      option.textContent = `${search.query} · ${sourceLabel}: ${label} · ${nutritionLabel}`;
      select.appendChild(option);
    }
    select.hidden = search.results.length === 0;
    if (
      search.results.some(
        (result) => String(result.bls_code ?? result.fdc_id) === selectedValue,
      )
    ) {
      select.value = selectedValue;
    } else if (search.results.length === 1) {
      select.value = String(search.results[0].bls_code ?? search.results[0].fdc_id);
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
        .week-navigation { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 20px 0 8px; }
        .week-navigation h3 { margin: 0; font-size: 1rem; font-weight: 750; }
        .week-navigation-actions { display: flex; gap: 8px; }
        .week-navigation-actions button { min-width: 40px; min-height: 38px; border: 1px solid var(--divider-color); border-radius: 11px; background: var(--secondary-background-color); color: var(--primary-text-color); font: inherit; font-weight: 700; cursor: pointer; }
        .week-navigation-actions button:disabled { opacity: .45; cursor: default; }
        .week-count { flex: 0 0 auto; padding: 8px 12px; border: 1px solid var(--divider-color); border-radius: 999px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: .8rem; font-weight: 700; }
        .week-plan-viewport { overflow-x: auto; padding: 2px 2px 10px; scrollbar-width: thin; }
        .week-plan-viewport:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .week-plan { display: grid; grid-template-columns: repeat(7, minmax(112px, 1fr)); min-width: 840px; gap: 10px; margin-bottom: 14px; }
        .week-day { display: flex; min-width: 0; flex-direction: column; padding: 10px; border: 1px solid var(--divider-color); border-radius: 18px; background: var(--secondary-background-color); overflow-wrap: anywhere; }
        .week-day h4 { display: flex; min-height: 2.5em; align-items: center; margin: 0 0 4px; padding: 2px 2px 10px; border-bottom: 1px solid var(--divider-color); font-size: .86rem; font-weight: 750; line-height: 1.25; text-transform: capitalize; }
        .day-calories { width: fit-content; margin: 2px 0 3px; padding: 4px 7px; border-radius: 999px; background: var(--primary-color); color: var(--text-primary-color, #fff); font-size: .64rem; font-weight: 750; }
        .shopping-preview { margin-top: 22px; padding: 18px; border: 1px solid var(--divider-color); border-radius: 18px; background: var(--secondary-background-color); }
        .shopping-preview header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
        .shopping-preview h3 { margin: 0; font-size: 1rem; }
        .shopping-preview ul { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px 18px; margin: 0; padding: 0; list-style: none; }
        .shopping-preview li { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); font-size: .88rem; }
        .shopping-empty { color: var(--secondary-text-color); font-size: .88rem; }
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
        .recipe-measure-hint { grid-column: 1 / -1; color: var(--secondary-text-color); font-size: .78rem; }
        .recipe-search { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--divider-color); border-radius: 14px; background: var(--secondary-background-color); }
        .recipe-search-controls { display: flex; gap: 8px; }
        .recipe-search-controls input { flex: 1; min-width: 0; }
        .recipe-search-results { display: grid; gap: 6px; max-height: 220px; overflow: auto; }
        .recipe-search-result { padding: 9px 11px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--ha-card-background, var(--card-background-color)); color: var(--primary-text-color); text-align: left; font: inherit; cursor: pointer; }
        .recipe-search-result:hover { border-color: var(--primary-color); }
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
        #saved_recipe_ingredients { margin: 8px 0 14px; padding-left: 22px; color: var(--primary-text-color); font-size: .88rem; line-height: 1.6; }
        #saved_recipe_instructions { white-space: pre-wrap; max-height: 260px; overflow: auto; color: var(--secondary-text-color); font-size: .88rem; line-height: 1.5; }
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
          <div class="week-navigation">
            <h3 id="selected_week_label">Aktuelle Woche</h3>
            <div class="week-navigation-actions">
              <button id="previous_week" type="button" aria-label="Aktuelle Woche anzeigen">‹</button>
              <button id="next_week" type="button" aria-label="Nächste Woche anzeigen">›</button>
            </div>
          </div>
          <div class="week-plan-viewport" role="region" aria-label="Wochenübersicht" tabindex="0">
            <div id="week_plan" class="week-plan"></div>
          </div>
          <section class="shopping-preview" aria-label="Einkaufsliste für ausgewählte Woche">
            <header>
              <h3>Einkaufsliste</h3>
              <button id="refresh_week_data" class="planner-button" type="button">Aktualisieren</button>
            </header>
            <ul id="shopping_items"></ul>
            <p id="shopping_empty" class="shopping-empty" hidden></p>
          </section>
          <div class="planner-actions">
            <button id="new_meal" class="planner-button" type="button">Neues Gericht</button>
            <button id="auto_plan" class="planner-button primary" type="button">Diese Woche automatisch planen</button>
          </div>
          <p id="status" class="meal-planner-status" role="status" aria-live="polite"></p>
        </div>
        <dialog id="meal_dialog">
          <h3 id="meal_dialog_title">Gericht auswählen</h3>
          <label for="meal_choice">Gespeichertes Gericht</label>
          <select id="meal_choice"></select>
          <p id="meal_choice_empty" hidden></p>
          <h4 id="saved_recipe_ingredients_heading" hidden>Zutaten</h4>
          <ul id="saved_recipe_ingredients" hidden></ul>
          <p id="saved_recipe_instructions" hidden></p>
          <a id="saved_recipe_source" hidden></a>
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
              <div class="recipe-search">
                <strong>Deutsche Rezepte im Wikibooks-Kochbuch suchen</strong>
                <div class="recipe-search-controls">
                  <input id="recipe_search_query" placeholder="z. B. Chicken Handi" maxlength="100" aria-label="Gericht suchen">
                  <button id="search_recipe" type="button">Suchen</button>
                </div>
                <p id="recipe_search_status" role="status" aria-live="polite"></p>
                <div id="recipe_search_results" class="recipe-search-results"></div>
                <small>Deutsche Rezepte aus Wikibooks. Lizenzhinweise auf der Originalseite beachten; Quelle wird gespeichert. Mengen prüfen und Nährwerte zuordnen.</small>
              </div>
              <input id="meal_name" placeholder="Gerichtname" maxlength="100" required>
              <label for="servings">Portionen pro Rezept</label>
              <input id="servings" type="number" min="1" max="100" value="2" required>
              <label for="nutrition_source">Nährwertdatenbank</label>
              <select id="nutrition_source" aria-label="Nährwertdatenbank">
                <option value="bls">BLS 4.0 · deutsche Lebensmittel</option>
                <option value="usda">USDA FoodData Central</option>
              </select>
              <small>BLS 4.0: Max Rubner-Institut (2025), CC BY 4.0 · <a href="https://doi.org/10.25826/Data20251217-134202-0" target="_blank" rel="noopener noreferrer">Datenquelle</a></small>
              <select id="meal_type" aria-label="Mahlzeit">
                <option value="lunch">Mittagessen</option>
              <option value="dinner">Abendessen</option>
              <option value="breakfast">Frühstück</option>
            </select>
            <div id="ingredients_container"></div>
            <label for="recipe_instructions">Zubereitung</label>
            <textarea id="recipe_instructions" rows="5" maxlength="20000"></textarea>
            <input id="recipe_source_url" type="hidden">
            <input id="recipe_source_name" type="hidden">
            <p>BLS-Daten: Bundeslebensmittelschlüssel 4.0, Max Rubner-Institut, CC BY 4.0. Nährwerte gelten je 100 g. Importierte Mengen prüfen; für „Stück“ Gewicht pro Stück angeben.</p>
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
    this.querySelector("#search_recipe").onclick = () =>
      this.searchRecipeCatalog();
    this.querySelector("#previous_week").onclick = () => this.changeWeek(-1);
    this.querySelector("#next_week").onclick = () => this.changeWeek(1);
    this.querySelector("#refresh_week_data").onclick = () =>
      this.loadWeekData(this._selectedWeekStart);
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
    this.querySelector("#nutrition_source").onchange = () => {
      for (const row of container.querySelectorAll(".ingredient-row")) {
        row._nutritionSearch = undefined;
        const matches = row.querySelector(".usda-match");
        matches.replaceChildren();
        matches.hidden = true;
        row.querySelector("button").textContent =
          this.querySelector("#nutrition_source").value === "bls"
            ? "BLS-Lebensmittel suchen"
            : "USDA-Treffer suchen";
      }
    };
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
      search.textContent =
        this.querySelector("#nutrition_source").value === "bls"
          ? "BLS-Lebensmittel suchen"
          : "USDA-Treffer suchen";
      const measureHint = document.createElement("small");
      measureHint.className = "recipe-measure-hint";
      measureHint.hidden = true;

      const matches = document.createElement("select");
      matches.className = "usda-match";
      matches.setAttribute("aria-label", "Nährwerttreffer auswählen");
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
          const source = this.querySelector("#nutrition_source").value;
          const serviceResult = await this._hass.callService(
            "weekly_meal_planner",
            "search_ingredient",
            { query, source },
            undefined,
            false,
            true,
          );
          const search = serviceResult?.response;
          if (
            search?.query?.toLocaleLowerCase() === query.toLocaleLowerCase() &&
            Array.isArray(search.results)
          ) {
            row._nutritionSearch = search;
            this.updateNutritionSearchResults(search);
          }
          const matches = row.querySelector(".usda-match");
          if (!search?.results?.length) {
            setStatus(
              source === "bls"
                ? `BLS fand keine passenden Lebensmittel für „${query}“.`
                : `USDA fand keine passenden Lebensmittel für „${query}“.`,
              true,
            );
            return;
          }
          if (!matches || matches.hidden || !matches.options.length) {
            throw new Error(
              "Nährwertsuche lieferte Treffer, Auswahl konnte nicht angezeigt werden.",
            );
          }
          setStatus(
            `${source === "bls" ? "BLS" : "USDA"}-Treffer geladen. Passenden Eintrag auswählen.`,
          );
        } catch (error) {
          setStatus(error.message || "Nährwertsuche fehlgeschlagen.", true);
        }
      };

      row.append(name, amount, unit, pieceWeight, search, matches, measureHint);
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
        const selectedResult = row._nutritionSearch?.results?.find(
          (match) =>
            String(match.bls_code ?? match.fdc_id) === selectedMatch.value,
        );
        if (!selectedResult) {
          setStatus(`Bitte für „${item}“ einen BLS- oder USDA-Treffer auswählen.`, true);
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
          ...(selectedResult.bls_code
            ? { bls_code: selectedResult.bls_code }
            : { fdc_id: Number(selectedResult.fdc_id) }),
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
          instructions: this.querySelector("#recipe_instructions").value.trim(),
          source_url: this.querySelector("#recipe_source_url").value.trim(),
          source_name: this.querySelector("#recipe_source_name").value.trim(),
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
      await this.loadWeekData(this._selectedWeekStart);
    };

    this.querySelector("#auto_plan").onclick = async () => {
      try {
        await this._hass.callService(
          "weekly_meal_planner",
          "generate_week_plan",
          { week_start: this._selectedWeekStart },
        );
        if (!(await this.loadWeekData(this._selectedWeekStart))) return;
        setStatus("Wochenplan und Einkaufsliste wurden aktualisiert.");
      } catch (error) {
        setStatus(error.message || "Wochenplan konnte nicht erstellt werden.", true);
      }
    };
  }
}

function parseRecipeMeasure(measure) {
  const match = String(measure).trim().match(
    /^(\d+(?:[.,]\d+)?|\d+\s*\/\s*\d+)\s*(kg|g|gr\.?|mg|ml|l)(?=$|[\s,;])/i,
  );
  if (!match) return undefined;
  const amountText = match[1].replace(",", ".");
  const amount = amountText.includes("/")
    ? amountText.split("/").map(Number).reduce((numerator, denominator) =>
      denominator ? numerator / denominator : Number.NaN)
    : Number(amountText);
  if (!Number.isFinite(amount) || amount <= 0) return undefined;
  const unit = match[2].replace(/\.$/, "").toLocaleLowerCase();
  return { amount, unit: unit === "gr" ? "g" : unit };
}

function mondayOf(day) {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}

if (!customElements.get("weekly-meal-planner-card")) {
  customElements.define("weekly-meal-planner-card", WeeklyMealPlannerCard);
}
