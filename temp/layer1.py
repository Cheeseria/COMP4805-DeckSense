# layer1.py
import json
import re
import ollama

ALLOWED_PRIMARY_ROLES = {
    "card advantage", "disruption", "ramp", "win condition", "value engine", "land",
}

# Expanded Keyword Hooks mapping
KEYWORD_HOOKS = {
    # Cost / Casting
    "kicker": "additional cost", "multikicker": "additional cost", "buyback": "additional cost",
    "escape": "alternative cost", "flashback": "alternative cost", "overload": "alternative cost", 
    "aftermath": "alternative cost", "disturb": "alternative cost", "madness": "alternative cost", 
    "foretell": "alternative cost", "suspend": "alternative cost", "delve": "cost reduction", 
    "convoke": "cost reduction", "improvise": "cost reduction", "affinity": "cost reduction",
    "prototype": "cost reduction", "casualty": "additional cost", "bargain": "additional cost",
    
    # Triggers / Casting
    "cascade": "cast trigger", "storm": "cast trigger", "prowess": "cast trigger", 
    "magecraft": "cast trigger", "ward": "protection", "hexproof": "protection", 
    "indestructible": "protection", "shroud": "protection",
    
    # Zone / Graveyard
    "cycling": "card selection", "landfall": "land trigger", "flash": "timing",
    "unearth": "recursion", "encore": "recursion", "embalm": "recursion", "eternalize": "recursion",
    
    # Combat / Evasion
    "flying": "evasion", "menace": "evasion", "trample": "evasion", "reach": "evasion", 
    "deathtouch": "combat", "first strike": "combat", "double strike": "combat",
    "haste": "combat", "vigilance": "combat", "lifelink": "lifegain",

    # Tokens / Counters
    "investigate": "artifact token", "amass": "creature token", "incubate": "creature token",
    "proliferate": "counter synergy", "toxic": "combat", "battle cry": "combat", "exalted": "combat",
    
    # Utility Mechanics
    "scry": "card selection", "surveil": "card selection", "connive": "card selection",
    "explore": "card selection", "plot": "alternative cost", "disguise": "alternative cost",
    "cloak": "alternative cost", "impending": "alternative cost", "saddle": "combat",
    "manifest": "card selection", "morph": "alternative cost", "megamorph": "alternative cost"
}

def _classify_ability_kind(ability: str) -> str:
    a = ability.strip().lower()
    if not a: return ""
    if re.match(r"^\{.*?\}:", a) or re.match(r"^\d+,\s*\{", a): return "activated"
    if a.startswith(("when ", "whenever ", "at the beginning of")): return "triggered"
    if "instead" in a or a.startswith("as ") or "enters the battlefield" in a: return "replacement"
    return "static"

def _extract_zone_transitions(text: str) -> list:
    t = text.lower()
    out = []
    if any(k in t for k in ("sacrifice", "dies", "destroy", "put into a graveyard", "mill")): out.append(("battlefield", "graveyard"))
    if "exile" in t: out.append(("battlefield", "exile"))
    if any(k in t for k in ("discard", "discards")): out.append(("hand", "graveyard"))
    if any(k in t for k in ("return to", "return it to", "return that card to", "return target")): out.append(("battlefield", "hand"))
    if any(k in t for k in ("draw a card", "draw two", "draw cards")): out.append(("library", "hand"))
    if "from your graveyard to your hand" in t: out.append(("graveyard", "hand"))
    if "from your graveyard to the battlefield" in t: out.append(("graveyard", "battlefield"))
    
    seen, uniq = set(), []
    for tr in out:
        if tr not in seen: seen.add(tr); uniq.append(tr)
    return [{"from": a, "to": b} for a, b in uniq]

def _extract_text_identifiers(text: str) -> list:
    """Extracts mechanical identifiers directly from the Oracle text."""
    t = text.lower()
    hooks = []
    
    # Casting & Trigger conditions
    if "whenever you cast" in t: hooks.append({"kind": "trigger:cast", "source": "oracle_text"})
    if "whenever an opponent casts" in t: hooks.append({"kind": "trigger:opponent_cast", "source": "oracle_text"})
    if "whenever a creature dies" in t: hooks.append({"kind": "trigger:dies", "source": "oracle_text"})
    if "whenever you draw" in t: hooks.append({"kind": "trigger:draw", "source": "oracle_text"})
    if "whenever you discard" in t: hooks.append({"kind": "trigger:discard", "source": "oracle_text"})
    if "whenever you sacrifice" in t: hooks.append({"kind": "trigger:sacrifice", "source": "oracle_text"})
    if "at the beginning of your upkeep" in t: hooks.append({"kind": "trigger:upkeep", "source": "oracle_text"})
    if "at the beginning of combat" in t: hooks.append({"kind": "trigger:combat", "source": "oracle_text"})
    
    # Costs & Mana
    if "as an additional cost" in t: hooks.append({"kind": "additional cost", "source": "oracle_text"})
    if "rather than pay" in t or "without paying its mana cost" in t: hooks.append({"kind": "alternative cost", "source": "oracle_text"})
    if "adds an additional" in t or "mana of any color" in t or "add {" in t: hooks.append({"kind": "mana_generator", "source": "oracle_text"})
    if "cost {" in t and ("less to cast" in t or "more to cast" in t): hooks.append({"kind": "cost_modifier", "source": "oracle_text"})
    if "treasure" in t: hooks.append({"kind": "artifact token", "source": "oracle_text"})
    
    # Engines & Statics
    if "you may play" in t or "you may cast" in t: hooks.append({"kind": "cast_from_zone", "source": "oracle_text"})
    if "any time you could cast a sorcery" in t: hooks.append({"kind": "timing_sorcery", "source": "oracle_text"})
    if "instead" in t: hooks.append({"kind": "replacement_effect", "source": "oracle_text"})
    
    # Recursion text
    if any(k in t for k in ("buyback", "flashback", "escape", "retrace", "jump-start", "from your graveyard to your hand", "return it to your hand", "cast it from your graveyard", "you may cast")):
        hooks.append({"kind": "recursion", "source": "oracle_text"})

    return hooks

def extract_card_facts(card) -> dict:
    text = (card.getText() or "").strip()
    abilities = [ln for ln in text.split("\n") if ln.strip()]
    ability_kinds = sorted({_classify_ability_kind(a) for a in abilities} - {""})

    keywords = list(getattr(card, "keywords", []) or [])
    keyword_hooks = sorted({KEYWORD_HOOKS[k.lower()] for k in keywords if k.lower() in KEYWORD_HOOKS})

    hooks = []
    # 1. Scryfall Keywords
    for kind in keyword_hooks: hooks.append({"kind": kind, "source": "scryfall_keyword"})
    # 2. Ability Types
    for ak in ability_kinds: hooks.append({"kind": f"ability:{ak}", "source": "oracle_text"})
    # 3. Zone Transitions
    for tr in _extract_zone_transitions(text):
        hooks.append({"kind": "zone_transition", "from": tr["from"], "to": tr["to"], "source": "oracle_text"})
    # 4. Text Identifiers
    hooks.extend(_extract_text_identifiers(text))

    seen, unique = set(), []
    for h in hooks:
        key = (h["kind"], h.get("from"), h.get("to"))
        if key not in seen:
            seen.add(key); unique.append(h)

    return {
        "name": card.getName(), "mana_cost": card.getCost() or "", "mana_value": getattr(card, "cmc", None),
        "type": card.getType() or "", "oracle_text": text, "statline": card.getStat() or "",
        "keywords": keywords, "color_identity": list(getattr(card, "color_identity", []) or []),
        "oracle_id": getattr(card, "oracle_id", None), "is_commander": bool(getattr(card, "is_commander", False)),
        "user_categories": sorted(getattr(card, "user_categories", set()) or []), "synergy": unique,
    }

SYSTEM_PROMPT = """
You are a strict Magic: The Gathering rules classification engine.
Analyze the provided card strictly by its Oracle Text and respond ONLY with valid JSON.
Allowed Primary Roles (use EXACTLY one, lowercase): card advantage, disruption, ramp, win condition, value engine, land.
Rules:
1. Do not invent non-existent mechanics.
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
  "synergy_hooks": [{{"kind": "string", "detail": "string"}}],
  "secondary_roles": [{{"role": "allowed role", "justification": "One sentence."}}]
}}
"""

def _validate_llm_output(parsed: dict, facts: dict) -> dict:
    out = {}
    role = str(parsed.get("primary_role", "")).strip().lower()
    if role not in ALLOWED_PRIMARY_ROLES:
        compact = re.sub(r"[^a-z]", "", role)
        role = next((r for r in ALLOWED_PRIMARY_ROLES if re.sub(r"[^a-z]", "", r) == compact), "value engine")
        out["_role_validation_failed"] = True
    out["primary_role"] = role
    out["summary"] = str(parsed.get("summary", "")).strip()
    out["justification"] = str(parsed.get("justification", "")).strip()
    out["synergy_hooks"] = parsed.get("synergy_hooks") or []
    out["secondary_roles"] = parsed.get("secondary_roles") or []
    
    for k in ("name", "mana_cost", "mana_value", "type", "oracle_text", "statline", "keywords", "color_identity", "oracle_id", "is_commander", "user_categories", "synergy"):
        out[k] = facts.get(k)
    return out

def _fallback(facts: dict, error: str) -> dict:
    out = {"primary_role": "value engine", "summary": "", "justification": "", "synergy_hooks": [], "secondary_roles": [], "_error": error}
    for k in ("name", "mana_cost", "mana_value", "type", "oracle_text", "statline", "keywords", "color_identity", "oracle_id", "is_commander", "user_categories", "synergy"):
        out[k] = facts.get(k)
    return out

def validate_card_role(facts: dict, model="qwen2.5:32b") -> dict:
    try:
        resp = ollama.chat(model=model, format="json", options={"temperature": 0, "num_ctx": 8192},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _user_prompt(facts)}])
        parsed = json.loads(resp["message"]["content"])
        if not isinstance(parsed, dict): raise ValueError("LLM returned non-object")
        return _validate_llm_output(parsed, facts)
    except Exception as e:
        return _fallback(facts, error=f"{type(e).__name__}: {e}")