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
        
        if cmc is not None and cmc <= 1 and any(x in mechs for x in ["mana generation", "mana addition"]):
            stats["fast_mana_count"] += 1
        if any(x in oracle for x in ["add {r}{r}{r}", "add {c}{c}", "add {r}{r}"]):
            stats["fast_mana_count"] += 1
            
        if any(x in mechs for x in ["counter spell", "creature removal", "damage dealing"]):
            stats["interaction_count"] += 1
            
    return stats

SYSTEM_PROMPT = """
You are an expert Magic: The Gathering Commander (EDH) power level assessor.
Your job is to assign a deck a Power Bracket (1-5) and estimate its win speed based on its RESOURCE GROWTH MODEL.

RESOURCE GROWTH MODEL:
EDH power levels correlate directly with how fast a deck's resources (mana, cards, board state) scale.
Analyze the Commander's Oracle Text and the Velocity Chains:
- LINEAR GROWTH (Bracket 2): Resources grow steadily. You play one land per turn, one spell per turn. Example: Playing a mana rock every turn.
- QUADRATIC / POLYNOMIAL GROWTH (Bracket 3): Resources compound. Spending mana draws cards, which draws more mana. Example: A value engine that draws 2 cards whenever you cast a spell.
- EXPONENTIAL GROWTH (Bracket 4-5): Resources multiply infinitely or near-infinitely in a single turn. Example: A Commander that reduces spell costs to {0}, allowing you to cast your entire deck in one turn, or an infinite combo loop.

EDH POWER BRACKETS:
- Bracket 1: Jank, theme decks. Wins turn 10+.
- Bracket 2 (Precon): Linear growth. Wins turn 8-9.
- Bracket 3 (Upgraded): Polynomial growth. Wins turn 6-7.
- Bracket 4 (Optimized): Exponential growth. Wins turn 4-5.
- Bracket 5 (cEDH): Immediate exponential growth. Wins turn 1-3.

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

STRATEGIC IDENTITY:
{l2b_analysis.get('deck_identity', 'Unknown')}

WIN CONDITIONS:
{json.dumps(l2b_analysis.get('win_conditions', []), indent=2)}

Return JSON matching this exact schema:
{{
  "growth_model": "Linear | Polynomial | Exponential",
  "growth_justification": "Explain how the Commander's text and the synergy engines create this growth rate.",
  "power_bracket": "1-5",
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
            "power_bracket": "Unknown",
            "estimated_win_turn": "Unknown"
        }
        
    parsed["_stats_used"] = stats
    return parsed