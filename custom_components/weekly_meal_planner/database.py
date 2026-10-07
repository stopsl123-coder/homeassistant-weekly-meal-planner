import sqlite3
import json

DB_PATH = "/config/mealplanner.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY,
            name TEXT,
            ingredients TEXT,
            meal_type TEXT
        )
    """)

    example_meals = [
        (
            "Rührei mit Toast",
            json.dumps({
                "Eier": {"amount": 3, "unit": "Stück", "calories": 72},
                "Toast": {"amount": 2, "unit": "Stück", "calories": 80},
                "Butter": {"amount": 10, "unit": "g", "calories": 75}
            }),
            "breakfast"
        ),
        (
            "Spaghetti Bolognese",
            json.dumps({
                "Spaghetti": {"amount": 200, "unit": "g", "calories": 350},
                "Hackfleisch": {"amount": 300, "unit": "g", "calories": 250},
                "Tomatensauce": {"amount": 250, "unit": "ml", "calories": 70}
            }),
            "lunch"
        ),
        (
            "Gemüsepfanne",
            json.dumps({
                "Paprika": {"amount": 2, "unit": "Stück", "calories": 30},
                "Zucchini": {"amount": 1, "unit": "Stück", "calories": 20},
                "Reis": {"amount": 150, "unit": "g", "calories": 180}
            }),
            "dinner"
        )
    ]

    for meal in example_meals:
        c.execute("INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)", meal)

    conn.commit()
    conn.close()

def add_meal(name, meal_type, ingredients_json):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)",
        (name, ingredients_json, meal_type)
    )
    conn.commit()
    conn.close()

def get_meals():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, ingredients, meal_type FROM meals")
    rows = c.fetchall()
    conn.close()

    return [{"name": r[0], "ingredients": json.loads(r[1]), "meal_type": r[2]} for r in rows]

def get_ingredients(meal_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ingredients FROM meals WHERE name=?", (meal_name,))
    row = c.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    return {}
