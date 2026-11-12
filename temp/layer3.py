# layer3.py
import json
import ollama
import requests
import time
from collections import Counter

_GAMECHANGER_CACHE = {"data": None, "timestamp": 0}

def get_gamechangers():
    """Fetches the official Game Changers list from Scryfall dynamically."""
    global _GAMECHANGER_CACHE
    
    if _GAMECHANGER_CACHE["data"] and (time.time() - _GAMECHANGER_CACHE["timestamp"] < 3600):
        return _GAMECHANGER_CACHE["data"]

    headers = {"User-Agent": "DeckSense/1.0 (Educational Project)"}
    url = "https://api.scryfall.com/cards/search?q=is%3Agamechanger&order=name"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        all_cards = [card["name"] for card in data.get("data", [])]
        
        while data.get("has_more"):
            next_page = data.get("next_page")
            response = requests.get(next_page, headers=headers, timeout=10)
            data = response.json()
            all_cards.extend([card["name"] for card in data.get("data", [])])
            
        _GAMECHANGER_CACHE["data"] = set(all_cards)
        _GAMECHANGER_CACHE["timestamp"] = time.time()
        print(f"[layer3] Fetched {len(all_cards)} Game Changers from Scryfall.")
        return _GAMECHANGER_CACHE["data"]
        
    except Exception as e:
        print(f"[layer3] Failed to fetch Game Changers: {e}. Using empty fallback.")
        return set()

def _calculate_deck_stats(graph, l2b_analysis):
    nodes = graph.get("interaction_nodes", [])
    gamechangers = get_gamechangers()
    
    stats = {
        "total_cards": len(nodes),
        "mana_curve": Counter(),
        "fast_mana_count": 0,
        "interaction_count": 0,
        "velocity_chain_count": len(l2b_analysis.get("velocity_chains", [])),
        "engine_count": len(l2b_analysis.get("functional_categories", [])),
        "game_changer_count": 0,
        "game_changer_list": []
    }
    
    for n in nodes:
        name = n.get("name")
        if name in gamechangers:
            stats["game_changer_count"] += 1
            stats["game_changer_list"].append(name)

        cmc = n.get("cmc")
        if cmc is not None:
            bucket = str(min(int(cmc), 7))
            stats["mana_curve"][bucket] += 1
            
        mechs = [m.lower() for m in n.get("mechanisms", [])]
        oracle = n.get("text", "").lower()
        
        if cmc is not None and cmc <= 1 and any(x in mechs for x in ["mana generation", "mana addition"]):
            stats["fast_mana_count"] += 1
        if any(x in oracle for x in ["add {r}{r}{r}", "add {c}{c}", "add {r}{r}"]):
            stats["fast_mana_count"] += 1
            
        if any(x in mechs for x in ["counter spell", "creature removal", "damage dealing"]):
            stats["interaction_count"] += 1
            
    return stats

SYSTEM_PROMPT = """
You are an expert Magic: The Gathering Commander (EDH) power level assessor.
You must output TWO brackets based on the data provided:
1. ESTIMATED BRACKET: Based on your analysis of the deck's synergy, resource growth, and velocity chains.
2. OFFICIAL BRACKET: Based strictly on Wizards of the Coast's hard rules regarding Game Changers.

WOTC OFFICIAL BRACKET RULES:
- Bracket 1 & 2: 0 Game Changers.
- Bracket 3: Maximum 3 Game Changers.
- Bracket 4: 4+ Game Changers (No limit).
- Bracket 5: cEDH (Optimized, no limit).
*Note: If the Game Changer count is > 3, the OFFICIAL bracket MUST be at least 4, regardless of how the deck plays.*

RESOURCE GROWTH MODEL (For Estimated Bracket):
- Linear Growth (Bracket 2)
- Polynomial Growth (Bracket 3)
- Exponential Growth (Bracket 4-5)

Return JSON format exactly matching the schema.
"""

def _user_prompt(commander_name, commander_text, stats, l2b_analysis):
    return f"""
Commander: {commander_name}
Commander Oracle Text: {commander_text}

DECK STATISTICS:
- Total Cards: {stats['total_cards']}
- Mana Curve: {dict(stats['mana_curve'])}
- Fast Mana Sources: {stats['fast_mana_count']}
- Interaction: {stats['interaction_count']}
- Velocity Chains Found: {stats['velocity_chain_count']}
- Functional Engines Found: {stats['engine_count']}
- GAME CHANGERS FOUND: {stats['game_changer_count']} (Cards: {', '.join(stats['game_changer_list']) if stats['game_changer_list'] else 'None'})

STRATEGIC IDENTITY:
{l2b_analysis.get('deck_identity', 'Unknown')}

WIN CONDITIONS:
{json.dumps(l2b_analysis.get('win_conditions', []), indent=2)}

Return JSON matching this exact schema:
{{
  "growth_model": "Linear | Polynomial | Exponential",
  "estimated_bracket": "1-5",
  "official_bracket": "1-5",
  "bracket_justification": "Explain the difference between the estimated and official brackets. Mention the Game Changer count.",
  "estimated_win_turn": "String (e.g. 'Turn 5-6')",
  "playstyle_summary": "2-3 sentences summarizing how the deck plays."
}}
"""

def assess_power_level(graph, l2b_analysis, commander_name, model="qwen2.5:32b"):
    stats = _calculate_deck_stats(graph, l2b_analysis)
    
    commander_text = "Unknown"
    for n in graph.get("interaction_nodes", []):
        if n["name"] == commander_name:
            commander_text = n.get("text", "")
            break

    try:
        resp = ollama.chat(
            model=model, format="json",
            options={"temperature": 0, "num_ctx": 4096},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(commander_name, commander_text, stats, l2b_analysis)}
            ]
        )
        parsed = json.loads(resp["message"]["content"])
    except Exception as e:
        return {
            "_error": str(e),
            "estimated_bracket": "Unknown",
            "official_bracket": "Unknown",
            "estimated_win_turn": "Unknown"
        }
        
    parsed["_stats_used"] = stats
    return parsed