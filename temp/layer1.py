# layer1.py
import json
import re
import ollama

ALLOWED_PRIMARY_ROLES = {
    "card advantage", "disruption", "ramp", "win condition", "value engine", "land",
}

KEYWORD_HOOKS = {
    "kicker": "additional_cost", "multikicker": "additional_cost",
    "buyback": "buyback", "escape": "graveyard_cast",
    "flashback": "graveyard_cast", "overload": "alternative_cost",
    "aftermath": "alternative_cost", "disturb": "alternative_cost",
    "madness": "alternative_cost", "foretell": "alternative_cost",
    "cascade": "cast_trigger", "storm": "cast_trigger", "prowess": "cast_trigger",
    "magecraft": "cast_trigger",
    "cycling": "card_selection", "landfall": "land_trigger", "flash": "timing",
    "unearth": "graveyard_cast", "encore": "graveyard_cast", "embalm": "graveyard_cast",
    "eternalize": "graveyard_cast", "scry": "card_selection", "surveil": "card_selection",
    "connive": "card_selection", "explore": "card_selection", "manifest": "card_selection",
    "investigate": "generates_treasure", "amass": "generates_treasure", "incubate": "generates_treasure",
    "convoke": "cost_reduction", "delve": "cost_reduction", "improvise": "cost_reduction",
    "affinity": "cost_reduction", "prototype": "cost_reduction",
    "flying": "evasion", "menace": "evasion", "trample": "evasion", "reach": "evasion",
    "haste": "combat", "vigilance": "combat", "first strike": "combat",
    "double strike": "combat", "deathtouch": "combat", "lifelink": "lifegain",
    "ward": "protection", "hexproof": "protection", "indestructible": "protection",
    "shroud": "protection", "toxic": "combat",
}

def _classify_ability_kind(ability: str) -> str:
    a = ability.strip().lower()
    if not a: return ""
    if re.match(r"^\{.*?\}:", a) or re.match(r"^\d+,\s*\{", a): return "activated"
    if a.startswith(("when ", "whenever ", "at the beginning of")): return "triggered"
    if "instead" in a or a.startswith("as ") or "enters the battlefield" in a: return "replacement"
    return "static"

def _extract_text_identifiers(text: str) -> list:
    t = text.lower()
    hooks = []
    if "add {" in t or "adds {" in t or "add one mana" in t:
        hooks.append({"kind": "generates_mana", "source": "oracle_text"})
    if "create" in t and ("treasure" in t or "clue" in t or "food" in t or "blood" in t):
        hooks.append({"kind": "generates_treasure", "source": "oracle_text"})
    if "draw" in t:
        hooks.append({"kind": "draws_cards", "source": "oracle_text"})
    if "whenever you cast" in t or "whenever you copy" in t:
        hooks.append({"kind": "cast_trigger", "source": "oracle_text"})
    if "copy target" in t or "copy it" in t or "copy that spell" in t:
        hooks.append({"kind": "copies_spells", "source": "oracle_text"})
    if "buyback" in t:
        hooks.append({"kind": "buyback", "source": "oracle_text"})
    if "flashback" in t or "escape" in t or "cast it from your graveyard" in t:
        hooks.append({"kind": "graveyard_cast", "source": "oracle_text"})
    if "less to cast" in t and "cost" in t:
        hooks.append({"kind": "cost_reduction", "source": "oracle_text"})
    if "without paying" in t or "rather than pay" in t:
        hooks.append({"kind": "free_cast", "source": "oracle_text"})
    if "as an additional cost" in t:
        hooks.append({"kind": "additional_cost", "source": "oracle_text"})
    if any(k in t for k in ("sacrifice", "dies", "destroy", "mill", "discard")):
        hooks.append({"kind": "graveyard_fill", "source": "oracle_text"})
    if "return target" in t and "graveyard" in t:
        hooks.append({"kind": "recursion", "source": "oracle_text"})
    return hooks

def extract_card_facts(card) -> dict:
    text = (card.getText() or "").strip()
    abilities = [ln for ln in text.split("\n") if ln.strip()]
    ability_kinds = sorted({_classify_ability_kind(a) for a in abilities} - {""})
    keywords = list(getattr(card, "keywords", []) or [])
    keyword_hooks = sorted({
        KEYWORD_HOOKS[k.lower()]
        for k in keywords
        if k.lower() in KEYWORD_HOOKS
    })

    hooks = []
    for kind in keyword_hooks:
        hooks.append({"kind": kind, "source": "scryfall_keyword"})
    for ak in ability_kinds:
        hooks.append({"kind": f"ability:{ak}", "source": "oracle_text"})
    hooks.extend(_extract_text_identifiers(text))

    seen, unique = set(), []
    for h in hooks:
        if h["kind"] not in seen:
            seen.add(h["kind"]); unique.append(h)

    return {
        "name": card.getName(),
        "mana_cost": card.getCost() or "",
        "mana_value": getattr(card, "cmc", None),
        "type": card.getType() or "",
        "oracle_text": text,
        "statline": card.getStat() or "",
        "keywords": keywords,
        "color_identity": list(getattr(card, "color_identity", []) or []),
        "oracle_id": getattr(card, "oracle_id", None),
        "is_commander": bool(getattr(card, "is_commander", False)),
        "user_categories": sorted(getattr(card, "user_categories", set()) or []),
        "synergy": unique,
    }


SYSTEM_PROMPT = """
You are a strict Magic: The Gathering rules classification engine.
Analyze the provided card strictly by its Oracle Text and respond ONLY with valid JSON.

Allowed Primary Roles (use EXACTLY one, lowercase):
- card advantage: draw, reanimate, or tutor/search. Cost reduction is NOT card advantage.
- disruption: counterspells, removal, board wipes, stax.
- ramp: mana acceleration, extra lands, treasures, cost reduction of spells.
- win condition: direct damage/drain, explicit combo pieces, heavy combat finishers.
- value engine: repeated resource advantage not covered above.
- land: lands and land-like mana sources with no other primary role.

You must ALSO extract two structural fields:
- "mechanisms": What does this card DO mechanically? Use short noun phrases.
- "domains": What does this card REQUIRE to function, and what does it PRODUCE?

CRITICAL SEMANTICS FOR DOMAINS:
"Produces" means the card makes a resource AVAILABLE to other cards.
"Requires" means the card CONSUMES a resource.
- Every card with a mana cost MUST include "Requires: Mana". The only exceptions are cards with mana cost 0 (lands, Lotus Petal, etc.).
- Recursion cards (buyback, flashback, escape, jump-start) MUST include BOTH "Produces: Card return to hand" AND "Requires: Card return to hand" — they consume mana to return themselves, and they produce a hand-returnable card as their effect.

Look at these exact examples to see how to translate Oracle text into structural domains:
- Sol Ring: {"Produces: Mana", "Requires: Tapped"}
- Storm-Kiln Artist: {"Requires: Instant/Sorcery cast", "Produces: Treasure token", "Produces: Mana"}
- Reiterate (buyback + spell copy): {"Requires: Instant/Sorcery cast", "Requires: Mana", "Produces: Spell copy", "Requires: Card return to hand", "Produces: Card return to hand"}
- Whispers of the Muse (buyback + draw): {"Requires: Mana", "Produces: Card draw", "Requires: Card return to hand", "Produces: Card return to hand"}
- Past in Flames: {"Requires: Instant/Sorcery in graveyard", "Produces: Cast from graveyard"}
- Underworld Breach: {"Requires: Nonland card in graveyard", "Produces: Cast from graveyard"}
- Buyback spells (Searing Touch, Haze of Rage): {"Produces: Card return to hand", "Requires: Mana", "Requires: Card return to hand"}
- Cost reducers (Vadrik, Goblin Electromancer, Mizzix): {"Produces: Cost reduction"}
- Card draw spells (Ponder, Preordain, Brainstorm): {"Requires: Mana", "Produces: Card draw"}

Note: Past in Flames and Underworld Breach both "Produce: Cast from graveyard" — that is the shared resource they enable.
Note: Treasures functionally produce Mana.

Rules:
1. Do not invent mechanics not present in the oracle text.
2. Keep justification to exactly ONE sentence based ONLY on Oracle text.
3. For primary_role, look at the RESULT of a triggered ability, not the trigger.
"""


def _user_prompt(f):
    return f"""
Card Data:
- Name: {f['name']}
- Type: {f['type']}
- Cost: {f['mana_cost'] or 'none'}
- Mana Value: {f.get('mana_value')}
- Keywords: {f['keywords']}
- Text: {f['oracle_text']}

Return JSON:
{{
  "primary_role": "one of: card advantage | disruption | ramp | win condition | value engine | land",
  "summary": "One sentence mechanical summary, Oracle text only.",
  "justification": "One sentence justifying primary_role.",
  "mechanisms": ["Mechanism 1", "Mechanism 2"],
  "domains": ["Requires: X", "Produces: Y"],
  "secondary_roles": [{{"role": "allowed role", "justification": "One sentence."}}]
}}
If empty, use empty arrays.
"""


def _validate_llm_output(parsed: dict, facts: dict) -> dict:
    out = {}
    role = str(parsed.get("primary_role", "")).strip().lower()
    if role not in ALLOWED_PRIMARY_ROLES:
        compact = re.sub(r"[^a-z]", "", role)
        role = next((r for r in ALLOWED_PRIMARY_ROLES
                     if re.sub(r"[^a-z]", "", r) == compact), "value engine")
        out["_role_validation_failed"] = True
    out["primary_role"] = role
    out["summary"] = str(parsed.get("summary", "")).strip()
    out["justification"] = str(parsed.get("justification", "")).strip()

    mechs = []
    for m in parsed.get("mechanisms") or []:
        if isinstance(m, str) and m.strip():
            mechs.append(m.strip())
    out["mechanisms"] = sorted(set(mechs))

    doms = []
    for d in parsed.get("domains") or []:
        if isinstance(d, str):
            ds = d.strip()
            low = ds.lower()
            if low.startswith("requires:") or low.startswith("produces:"):
                doms.append(ds)
    out["domains"] = sorted(set(doms))

    sec = []
    for s in parsed.get("secondary_roles") or []:
        if isinstance(s, dict) and "role" in s:
            r = str(s["role"]).strip().lower()
            if r in ALLOWED_PRIMARY_ROLES:
                sec.append({"role": r,
                            "justification": str(s.get("justification", "")).strip()})
    out["secondary_roles"] = sec

    for k in ("name", "mana_cost", "mana_value", "type", "oracle_text", "statline",
              "keywords", "color_identity", "oracle_id", "is_commander",
              "user_categories", "synergy"):
        out[k] = facts.get(k)
    return out


def _fallback(facts: dict, error: str) -> dict:
    out = {
        "primary_role": "value engine", "summary": "", "justification": "",
        "mechanisms": [], "domains": [], "secondary_roles": [], "_error": error,
    }
    for k in ("name", "mana_cost", "mana_value", "type", "oracle_text", "statline",
              "keywords", "color_identity", "oracle_id", "is_commander",
              "user_categories", "synergy"):
        out[k] = facts.get(k)
    return out


def validate_card_role(facts: dict, model="qwen2.5:32b") -> dict:
    try:
        resp = ollama.chat(
            model=model, format="json", options={"temperature": 0, "num_ctx": 8192},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(facts)},
            ],
        )
        parsed = json.loads(resp["message"]["content"])
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned {type(parsed).__name__}, expected object")
    except Exception as e:
        return _fallback(facts, error=f"{type(e).__name__}: {e}")
    try:
        return _validate_llm_output(parsed, facts)
    except Exception as e:
        return _fallback(facts, error=f"validation: {type(e).__name__}: {e}")