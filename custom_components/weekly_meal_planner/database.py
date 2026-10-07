import sqlite3
import json

DB_PATH = "/config/mealplanner.db"

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
    return json.loads(row[0]) if row else {}
