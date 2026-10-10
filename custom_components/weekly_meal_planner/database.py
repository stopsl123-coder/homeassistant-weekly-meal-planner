"""SQLite persistence for meals and the current weekly plan."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
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
            if "servings" not in columns:
                connection.execute(
                    "ALTER TABLE meals ADD COLUMN servings INTEGER NOT NULL DEFAULT 1"
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS nutrition_cache (
                    fdc_id INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    nutrition TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS nutrition_searches (
                    query TEXT PRIMARY KEY COLLATE NOCASE,
                    results TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
                """
            )

    def add_meal(
        self,
        name: str,
        meal_type: str,
        servings: int,
        ingredients: dict[str, dict[str, Any]],
    ) -> None:
        serialized = json.dumps(
            ingredients, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE meals SET ingredients = ?, meal_type = ?, servings = ?
                WHERE name = ?
                """,
                (serialized, meal_type, servings, name),
            )
            if cursor.rowcount == 0:
                connection.execute(
                    """
                    INSERT INTO meals (name, ingredients, meal_type, servings)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, serialized, meal_type, servings),
                )

    def get_meals(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, ingredients, meal_type, servings FROM meals ORDER BY name"
            ).fetchall()
        return [
            {
                "name": row["name"],
                "ingredients": json.loads(row["ingredients"]),
                "meal_type": row["meal_type"],
                "servings": row["servings"],
            }
            for row in rows
        ]

    def get_meal(self, name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, ingredients, meal_type, servings FROM meals
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
            "servings": row["servings"],
        }

    def cache_nutrition_search(
        self, query: str, results: list[dict[str, Any]]
    ) -> None:
        cached_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            for result in results:
                connection.execute(
                    """
                    INSERT INTO nutrition_cache
                        (fdc_id, description, nutrition, cached_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fdc_id) DO UPDATE SET
                        description = excluded.description,
                        nutrition = excluded.nutrition,
                        cached_at = excluded.cached_at
                    """,
                    (
                        result["fdc_id"],
                        result["description"],
                        json.dumps(result["nutrition"], allow_nan=False),
                        cached_at,
                    ),
                )
            connection.execute(
                """
                INSERT INTO nutrition_searches (query, results, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(query) DO UPDATE SET
                    results = excluded.results, cached_at = excluded.cached_at
                """,
                (
                    query.strip(),
                    json.dumps(results, ensure_ascii=False, allow_nan=False),
                    cached_at,
                ),
            )

    def get_nutrition_search(
        self, query: str, max_age_seconds: int = 604_800
    ) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT results, cached_at FROM nutrition_searches
                WHERE query = ? COLLATE NOCASE
                """,
                (query.strip(),),
            ).fetchone()
        if row is None:
            return None
        cached_at = datetime.fromisoformat(row["cached_at"])
        if (datetime.now(UTC) - cached_at).total_seconds() > max_age_seconds:
            return None
        return json.loads(row["results"])

    def get_cached_nutrition(
        self, fdc_id: int, max_age_seconds: int = 604_800
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT description, nutrition, cached_at FROM nutrition_cache
                WHERE fdc_id = ?
                """,
                (fdc_id,),
            ).fetchone()
        if row is None:
            return None
        cached_at = datetime.fromisoformat(row["cached_at"])
        if (datetime.now(UTC) - cached_at).total_seconds() > max_age_seconds:
            return None
        return {
            "description": row["description"],
            "nutrition": json.loads(row["nutrition"]),
        }

    def get_latest_nutrition_search(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT query, results FROM nutrition_searches
                ORDER BY cached_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            return {"query": "", "results": []}
        return {"query": row["query"], "results": json.loads(row["results"])}

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

    def get_recent_meal_usage(self, week_start: str) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT meal_name, COUNT(*) AS uses FROM week_plan
                WHERE day >= date(?, '-21 days') AND day < ?
                GROUP BY meal_name
                """,
                (week_start, week_start),
            ).fetchall()
        return {row["meal_name"]: row["uses"] for row in rows}
