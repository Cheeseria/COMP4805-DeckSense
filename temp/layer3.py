# layer3.py
import json
import ollama
from collections import Counter

def _calculate_deck_stats(graph, l2b_analysis):
    """Calculate deterministic stats from the graph and Layer 2b analysis."""
    nodes = graph.get("interaction_nodes", [])
    
    stats = {
        "total_cards": len(nodes),
        "mana_curve": Counter(),
        "fast_mana_count": 0,
        "interaction_count": 0,
        "velocity_chain_count": len(l2b_analysis.get("velocity_chains", [])),
        "engine_count": len(l2b_analysis.get("functional_categories", []))
    }
    
    for n in nodes:
        cmc = n.get("cmc")
        if cmc is not None:
            bucket = str(min(int(cmc), 7))
            stats["mana_curve"][bucket] += 1
            
        mechs = [m.lower() for m in n.get("mechanisms", [])]
        oracle = n.get("text", "").lower()
        
        # Count fast mana
        if cmc is not None and cmc <= 1 and any(x in mechs for x in ["mana generation", "mana addition"]):
            stats["fast_mana_count"] += 1
        if any(x in oracle for x in ["add {r}{r}{r}", "add {c}{c}", "add {r}{r}"]):
            stats["fast_mana_count"] += 1
            
        # Count interaction
        if any(x in mechs for x in ["counter spell", "creature removal", "damage dealing"]):
            stats["interaction_count"] += 1
            
    return stats

SYSTEM_PROMPT = """
You are an expert Magic: The Gathering Commander (EDH) power level assessor.
You are given the statistical breakdown of a deck, its strategic analysis, and the Oracle Text of its Commander.
Your job is to assign it a Power Bracket (1-5) and estimate its average win speed.

GENERAL RULE FOR COMMANDER EFFICIENCY:
The Commander is always available from the Command Zone. If the Commander's Oracle Text provides a persistent, scalable resource advantage (e.g., generating mana, reducing costs, creating tokens, or drawing cards based on a scalable metric), the deck's effective power and speed are significantly higher than its base mana curve suggests. 
Consider this when assigning the Bracket. Do not assume a deck is low power just because its average CMC is high if the Commander offsets that cost.

EDH POWER BRACKETS (Official):
- Bracket 1 (Exhibition): Jank, theme decks, no fast mana, wins turn 10+.
- Bracket 2 (Core/Precon): Average decks, some interaction, wins turn 8-9.
- Bracket 3 (Upgraded): Focused strategies, good mana base, some fast mana, wins turn 6-7.
- Bracket 4 (Optimized): High power, efficient combos, fast mana, wins turn 4-5.
- Bracket 5 (cEDH): Competitive, max efficiency, wins turn 1-3.

Return JSON format exactly matching the schema.
"""

def _user_prompt(commander_name, commander_text, stats, l2b_analysis):
    return f"""
Commander: {commander_name}
Commander Oracle Text: {commander_text}

DECK STATISTICS:
- Total Cards: {stats['total_cards']}
- Mana Curve: {dict(stats['mana_curve'])}
- Fast Mana Sources (0-2 CMC or Rituals): {stats['fast_mana_count']}
- Interaction: {stats['interaction_count']}
- Velocity Chains Found: {stats['velocity_chain_count']}
- Functional Engines Found: {stats['engine_count']}

STRATEGIC IDENTITY:
{l2b_analysis.get('deck_identity', 'Unknown')}

WIN CONDITIONS:
{json.dumps(l2b_analysis.get('win_conditions', []), indent=2)}

Return JSON matching this exact schema:
{{
  "power_bracket": "1-5",
  "bracket_justification": "2-3 sentences explaining why this bracket, specifically referencing how the Commander's text and the stats interact.",
  "estimated_win_turn": "String (e.g. 'Turn 5-6')",
  "playstyle_summary": "2-3 sentences summarizing how the deck plays."
}}
"""

def assess_power_level(graph, l2b_analysis, commander_name, model="qwen2.5:32b"):
    stats = _calculate_deck_stats(graph, l2b_analysis)
    
    # Extract the Commander's text from the graph data
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
            "power_bracket": "Unknown",
            "bracket_justification": "Failed to parse.",
            "estimated_win_turn": "Unknown",
            "playstyle_summary": "Unknown"
        }
        
    parsed["_stats_used"] = stats
    return parsed