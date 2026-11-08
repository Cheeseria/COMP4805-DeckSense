# ingest.py
"""
Ingestion: Archidekt deck -> list[Card], enriched from Scryfall.

Key fixes vs. old version:
  - branch on Scryfall 'layout' for DFC vs adventure (adventures crash the old code)
  - no double-counting DFCs
  - merge categories into one Card's user_categories (was: duplicate Cards)
  - capture is_commander from Archidekt's `isCommander` flag
  - .get() everywhere; HTTP status handling + retry/backoff
  - disk cache for Scryfall responses (reproducibility)
  - returns (deck_cards, commander_name, deck_id)
"""
import json
import os
import time
import hashlib
import warnings

import requests
import pyrchidekt.api
from time import sleep

import card as Cards

warnings.filterwarnings("ignore")

SCRYFALL_CACHE_DIR = "cache/scryfall"
os.makedirs(SCRYFALL_CACHE_DIR, exist_ok=True)

USER_AGENT = "DeckSense/1.0 (Educational Project)"
SCRYFALL_NAMED = "https://api.scryfall.com/cards/named"


def _scryfall_cache_path(name: str) -> str:
    key = hashlib.sha1(name.lower().encode("utf-8")).hexdigest()[:20]
    return os.path.join(SCRYFALL_CACHE_DIR, f"{key}.json")


def _fetch_scryfall_fuzzy(name: str, retries: int = 3) -> dict | None:
    """Return Scryfall card JSON or None. Retries on 429/5xx; caches on disk."""
    cache_path = _scryfall_cache_path(name)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass  # fall through and re-fetch

    delay = 1.0
    for attempt in range(retries):
        try:
            r = requests.get(
                SCRYFALL_NAMED,
                params={"fuzzy": name},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
        except requests.RequestException as e:
            print(f"[scryfall] request error for {name!r}: {e}")
            sleep(delay); delay *= 2; continue

        if r.status_code == 200:
            data = r.json()
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        if r.status_code == 404:
            print(f"[scryfall] 404 for {name!r}")
            return None
        if r.status_code == 429 or 500 <= r.status_code < 600:
            sleep(delay); delay *= 2; continue
        print(f"[scryfall] unexpected {r.status_code} for {name!r}")
        return None
    return None


def _is_commander_card(card_obj, categories) -> bool:
    """Detect commander from Archidekt metadata (attribute names vary by wrapper)."""
    flag = getattr(card_obj, "is_commander", None)
    if flag is True:
        return True
    for cat in categories or []:
        name = getattr(cat, "name", str(cat)).lower()
        if "commander" in name:
            return True
    return False


def parseArchiURL(url):
    """Parse an Archidekt deck URL.

    Returns (deck: list[Card], commander_name: str | None, deck_id: str)
    """
    parts = url.rstrip("/").split("/")
    deck_id = parts[-2]  # yields "6429634", correct
    deckAPI = pyrchidekt.api.getDeckById(deck_id)

    # Scryfall enforces ~2 req/s per IP; we sleep 0.5s per unique card.
    # A 100-card deck takes ~50s cold, instant warm from disk cache.
    deck = []
    commander_name = None
    seen_oracle_ids = set()  # guard against multi-category duplicates

    for category in deckAPI.categories:
        cat_name = getattr(category, "name", str(category))
        for card_obj in category.cards:
            oracle_card = card_obj.card.oracle_card
            name = oracle_card.name
            quantity = getattr(card_obj, "quantity", 1) or 1
            is_cmd = _is_commander_card(card_obj, [category])

            card_json = _fetch_scryfall_fuzzy(name)
            sleep(0.5)  # rate limit AFTER the request, next iteration pays it
            if card_json is None:
                print(f"[ingest] skipping unresolved card: {name!r}")
                continue

            layout = card_json.get("layout", "")
            faces = card_json.get("card_faces")
            is_dfc = layout in {"transform", "modal_dfc", "double_faced_token"} and faces
            # 'adventure', 'split', 'flip', 'prepare' have combined oracle_text and NO faces

            if is_dfc:
                # One Card for the whole DFC (do NOT double-count).
                # Combine faces' oracle text; use front face for cost/type.
                front, back = faces[0], faces[1] if len(faces) > 1 else faces[0]
                combined_text = (front.get("oracle_text", "") or "") + "\n//\n" + (
                    back.get("oracle_text", "") or ""
                )
                face_json = {
                    "name": card_json.get("name", front.get("name", name)),
                    "mana_cost": front.get("mana_cost", "") or "",
                    "oracle_text": combined_text,
                    "type_line": front.get("type_line", "") or "",
                    "power": front.get("power"),
                    "toughness": front.get("toughness"),
                    "loyalty": front.get("loyalty"),
                    "defense": front.get("defense"),
                    "keywords": card_json.get("keywords", []) or [],
                    "cmc": card_json.get("cmc"),
                    "color_identity": card_json.get("color_identity", []) or [],
                    "oracle_id": card_json.get("oracle_id"),
                }
                new_card = Cards.createCard(face_json, quantity, cat_name,
                                            is_commander=is_cmd,
                                            user_categories=[cat_name])
            else:
                new_card = Cards.createCard(card_json, quantity, cat_name,
                                            is_commander=is_cmd,
                                            user_categories=[cat_name])

            if new_card.oracle_id and new_card.oracle_id in seen_oracle_ids:
                # Merge categories into the existing Card instead of duplicating
                for existing in deck:
                    if existing.oracle_id == new_card.oracle_id:
                        existing.user_categories |= new_card.user_categories
                        existing.is_commander = existing.is_commander or new_card.is_commander
                        break
                continue

            seen_oracle_ids.add(new_card.oracle_id)
            deck.append(new_card)

            if new_card.is_commander and not commander_name:
                commander_name = new_card.name

    return deck, commander_name, deck_id