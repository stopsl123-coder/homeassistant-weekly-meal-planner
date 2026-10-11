"""German Wikibooks cookbook search client."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import aiohttp

WIKIBOOKS_API_URL = "https://de.wikibooks.org/w/api.php"
WIKIBOOKS_PAGE_URL = "https://de.wikibooks.org/wiki/"
WIKIBOOKS_SOURCE_NAME = "Wikibooks Kochbuch"
_RECIPE_TITLE_PREFIX = "Kochbuch/ "
_HEADING = re.compile(r"^==+\s*(.*?)\s*==+\s*$", re.MULTILINE)
_QUANTITY = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?"
    r"(?:\s*(?:kg|g|gr\.?|mg|ml|l|el|tl|esslöffel|teelöffel|"
    r"stück|stk\.?|prise|prisen|bund|dose|dosen|packung|päckchen|"
    r"zehe|zehen|scheibe|scheiben|tasse|tassen))?\.?)\s+(.+?)\s*$",
    re.IGNORECASE,
)


async def search_recipes(
    session: aiohttp.ClientSession, query: str
) -> list[dict[str, Any]]:
    """Search recipes in the German Wikibooks cookbook and parse their content."""
    timeout = aiohttp.ClientTimeout(total=20)
    async with session.get(
        WIKIBOOKS_API_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": f'intitle:Kochbuch/ intitle:"{query}"',
            "srnamespace": 0,
            "srlimit": 10,
            "format": "json",
        },
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        search_data = await response.json()

    search_result = (
        search_data.get("query") if isinstance(search_data, dict) else None
    )
    if not isinstance(search_result, dict):
        raise ValueError("Wikibooks lieferte ungültige Suchergebnisse.")
    pages = [
        result
        for result in search_result.get("search", [])
        if isinstance(result, dict)
        and str(result.get("title", "")).startswith(_RECIPE_TITLE_PREFIX)
        and int(result.get("wordcount", 0)) < 5_000
    ]
    if not pages:
        return []

    page_ids = "|".join(str(page["pageid"]) for page in pages)
    async with session.get(
        WIKIBOOKS_API_URL,
        params={
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "pageids": page_ids,
            "format": "json",
        },
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        content_data = await response.json()

    if not isinstance(content_data, dict):
        raise ValueError("Wikibooks lieferte ungültige Rezeptdaten.")
    content_result = content_data.get("query")
    content_pages = (
        content_result.get("pages") if isinstance(content_result, dict) else None
    )
    if not isinstance(content_pages, dict):
        raise ValueError("Wikibooks lieferte ungültige Rezeptseiten.")
    recipes = []
    for page in pages:
        content = content_pages.get(str(page["pageid"]), {})
        if not isinstance(content, dict):
            continue
        revisions = content.get("revisions", [])
        if not isinstance(revisions, list) or not revisions:
            continue
        revision = revisions[0]
        slots = revision.get("slots", {}) if isinstance(revision, dict) else {}
        main_slot = slots.get("main", {}) if isinstance(slots, dict) else {}
        revision_content = main_slot.get("*", "") if isinstance(main_slot, dict) else ""
        recipe = parse_wikibooks_recipe(
            str(page.get("title", "")),
            str(revision_content),
        )
        if recipe is not None:
            recipes.append(recipe)
    return recipes


def parse_wikibooks_recipe(title: str, content: str) -> dict[str, Any] | None:
    """Extract ingredients and instructions from a German Wikibooks recipe."""
    if not title.startswith(_RECIPE_TITLE_PREFIX):
        return None
    sections = _sections(content)
    ingredient_section = next(
        (
            text
            for heading, text in sections
            if heading.casefold().startswith("zutaten")
        ),
        "",
    )
    instruction_section = next(
        (
            text
            for heading, text in sections
            if heading.casefold().startswith(
                ("zubereitung", "fortschritte", "anleitung")
            )
        ),
        "",
    )
    if not ingredient_section and not instruction_section:
        return None

    heading = next(
        (
            section_heading
            for section_heading, _ in sections
            if section_heading.casefold().startswith("zutaten")
        ),
        "",
    )
    servings_match = re.search(r"\b(\d+)\s+(?:personen|portionen)\b", heading, re.I)
    if not servings_match:
        servings_match = re.search(
            r"\|\s*Portionen\s*=\s*(\d+)", content, re.IGNORECASE
        )
    ingredients = _parse_ingredients(ingredient_section)
    return {
        "id": title,
        "name": title.removeprefix("Kochbuch/").strip(),
        "servings": int(servings_match.group(1)) if servings_match else 2,
        "instructions": _plain_text(
            re.split(r"(?im)^\s*'{3,}\s*Erfasst von:", instruction_section, maxsplit=1)[0]
        ).strip(),
        "source_url": f"{WIKIBOOKS_PAGE_URL}{quote(title.replace(' ', '_'))}",
        "source": WIKIBOOKS_SOURCE_NAME,
        "ingredients": ingredients,
    }


def _sections(content: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(content))
    return [
        (
            match.group(1).strip(),
            content[match.end() : matches[index + 1].start() if index + 1 < len(matches) else None],
        )
        for index, match in enumerate(matches)
    ]


def _parse_ingredients(section: str) -> list[dict[str, str]]:
    ingredients = []
    for line in _plain_text(section).splitlines():
        item = line.strip()
        if not item or item.endswith(":"):
            continue
        match = _QUANTITY.match(item)
        if match:
            measure, name = match.groups()
            name = name.strip(" -–")
        else:
            measure, name = "", item.strip(" -–")
        if name:
            ingredients.append({"name": name, "measure": measure.strip()})
    return ingredients


def _plain_text(value: str) -> str:
    text = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    text = re.sub(r"\[\[(?:Kategorie|Category):[^\]]+\]\]", "", text, flags=re.I)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^]]+)\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"^\s*[*#;]+\s*", "", text, flags=re.MULTILINE)
    return text
