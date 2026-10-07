import requests

API_KEY = None

def set_api_key(key):
    global API_KEY
    API_KEY = key

def get_nutrition_for_item(item_name):
    if not API_KEY:
        raise RuntimeError("USDA API-Key nicht gesetzt!")

    params = {
        "api_key": API_KEY,
        "query": item_name,
        "pageSize": 1
    }

    response = requests.get("https://api.nal.usda.gov/fdc/v1/foods/search", params=params)
    response.raise_for_status()
    data = response.json()

    if "foods" not in data or len(data["foods"]) == 0:
        return None

    food = data["foods"][0]
    nutrients = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}

    return {
        "calories_per_100g": nutrients.get("Energy", 0),
        "protein": nutrients.get("Protein", 0),
        "fat": nutrients.get("Total lipid (fat)", 0),
        "carbs": nutrients.get("Carbohydrate, by difference", 0)
    }
