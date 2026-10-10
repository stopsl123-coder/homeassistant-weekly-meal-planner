"""SQLite persistence for meals and the current weekly plan."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class MealPlannerDatabase:
    """Store recipes and planned meals in Home Assistant's configuration folder."""

    def __init__(self, path: str) -> None:
        self.path = path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create new tables without replacing existing recipe data."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meals (
                    name TEXT NOT NULL,
                    ingredients TEXT NOT NULL,
                    meal_type TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(meals)")
            }
            if not {"name", "ingredients", "meal_type"}.issubset(columns):
                raise sqlite3.DatabaseError(
                    "Existing meals table has an unsupported schema"
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS week_plan (
                    day TEXT NOT NULL,
                    meal_type TEXT NOT NULL,
                    meal_name TEXT NOT NULL,
                    PRIMARY KEY (day, meal_type)
                )
                """
            )

    def add_meal(
        self, name: str, meal_type: str, ingredients: dict[str, dict[str, Any]]
    ) -> None:
        serialized = json.dumps(
            ingredients, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE meals SET ingredients = ?, meal_type = ? WHERE name = ?",
                (serialized, meal_type, name),
            )
            if cursor.rowcount == 0:
                connection.execute(
                    "INSERT INTO meals (name, ingredients, meal_type) VALUES (?, ?, ?)",
                    (name, serialized, meal_type),
                )

    def get_meals(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, ingredients, meal_type FROM meals ORDER BY name"
            ).fetchall()
        return [
            {
                "name": row["name"],
                "ingredients": json.loads(row["ingredients"]),
                "meal_type": row["meal_type"],
            }
            for row in rows
        ]

    def get_meal(self, name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, ingredients, meal_type FROM meals
                WHERE name = ? ORDER BY rowid DESC LIMIT 1
                """,
                (name,),
            ).fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "ingredients": json.loads(row["ingredients"]),
            "meal_type": row["meal_type"],
        }

    def replace_week_plan(
        self, week_start: str, plan: dict[str, dict[str, str]]
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM week_plan WHERE day >= ? AND day < date(?, '+7 days')",
                (week_start, week_start),
            )
            connection.executemany(
                """
                INSERT INTO week_plan (day, meal_type, meal_name)
                VALUES (?, ?, ?)
                """,
                [
                    (day, meal_type, meal_name)
                    for day, meals in plan.items()
                    for meal_type, meal_name in meals.items()
                ],
            )

    def get_week_plan(self, week_start: str) -> dict[str, dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT day, meal_type, meal_name FROM week_plan
                WHERE day >= ? AND day < date(?, '+7 days')
                ORDER BY day, meal_type
                """,
                (week_start, week_start),
            ).fetchall()
        plan: dict[str, dict[str, str]] = {}
        for row in rows:
            plan.setdefault(row["day"], {})[row["meal_type"]] = row["meal_name"]
        return plan
