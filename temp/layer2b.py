# layer2b.py
import json
import ollama
from collections import defaultdict

def _build_functional_groups(graph):
    """Group all cards by the mechanisms extracted by Layer 1."""
    nodes = graph.get("interaction_nodes", [])
    groups = defaultdict(list)
    
    for n in nodes:
        name = n["name"]
        mechs = n.get("mechanisms", [])
        
        if "land" in n.get("type", "").lower():
            groups["Lands"].append(name)
            continue
            
        if not mechs:
            groups["Unclassified"].append(name)
        else:
            for m in mechs:
                groups[m.title()].append(name)
                
    lines = []
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    
    for group_name, cards in sorted_groups:
        if len(cards) > 1:
            lines.append(f"**{group_name}** ({len(cards)} cards): {', '.join(cards)}")
            
    return "\n\n".join(lines)

def _build_cross_group_bridges(graph):
    """Find edges connecting cards with different primary mechanisms."""
    nodes = {n["name"]: n for n in graph.get("interaction_nodes", [])}
    
    def get_primary_mech(name):
        mechs = nodes.get(name, {}).get("mechanisms", [])
        if not mechs: return "Unknown"
        return mechs[0].title()

    edges = graph.get("interaction_edges", [])
    cross_edges = []
    seen = set()

    for e in edges:
        s_mech = get_primary_mech(e["source"])
        t_mech = get_primary_mech(e["target"])
        
        if s_mech != t_mech and s_mech != "Unknown" and t_mech != "Unknown":
            key = f"{e['source']}->{e['target']}"
            if key in seen: continue
            seen.add(key)
            
            si = nodes.get(e["source"], {})
            ti = nodes.get(e["target"], {})
            s_doms = " | ".join(si.get("domains", [])[:2])
            t_doms = " | ".join(ti.get("domains", [])[:2])
            
            cross_edges.append(
                f"- [{s_mech}] '{e['source']}' ({s_doms}) --> [{t_mech}] '{e['target']}' ({t_doms})"
            )

    return "\n".join(cross_edges[:150])

SYSTEM_PROMPT_TEMPLATE = """
You are a competitive Magic: The Gathering strategist specializing in Commander (EDH).
Your job is to analyze the provided deck data and extract its core strategic identity, focusing on synergy and velocity chains.

DEFINITIONS:
- SYNERGY ENGINE: A group of cards that generate value by triggering each other (e.g., casting spells to trigger draw and mana generation).
- VELOCITY CHAIN: A sequence of plays where each card fuels the next, building massive advantage (e.g., a "Storm" chain, or a board-state snowball). It does not need to be a mathematically infinite loop, just a highly synergistic path to victory.
- WIN CONDITION: The specific way the deck actually ends the game (e.g., combat damage, draining life, milling out).

ANALYSIS REQUIREMENTS:
1. Group the cards into FUNCTIONAL CATEGORIES (Mana, Card Draw, Payoffs, etc.).
2. Explain the INTERCATEGORIAL SYNERGY (how the groups connect).
3. Map out 1-3 Velocity Chains. Explicitly name the cards that build the advantage and the cards that keep the hand full (refueling).
4. Identify the primary Win Conditions.

STRICT DEAD WEIGHT RULE:
You may ONLY list a card in "dead_weight_candidates" if it appears in the CANDIDATE ISOLATED CARDS list provided below. If a card has graph edges, it is FORBIDDEN from being called dead weight.
"""

def _user_prompt(commander_name, groups_text, bridges_text, isolated):
    return f"""
Commander: {commander_name}

DATA PROVIDED:
FUNCTIONAL GROUPS (Pre-processed):
{groups_text}

CROSS-GROUP BRIDGES (Pre-processed):
{bridges_text}

CANDIDATE ISOLATED CARDS:
{json.dumps(isolated, indent=2)}

Return JSON matching this exact schema:
{{
  "deck_identity": "2-3 sentence summary of the strategy.",
  "functional_categories": [
    {{
      "category_name": "String",
      "key_cards": ["A", "B"],
      "explanation": "What this group does."
    }}
  ],
  "intercategorial_synergy": [
    {{
      "groups_involved": ["Group A", "Group B"],
      "explanation": "How Group A fuels Group B (Cause and Effect)."
    }}
  ],
  "velocity_chains": [
    {{
      "chain_name": "String",
      "key_cards": ["A", "B", "C"],
      "refueling_cards": ["Card that draws"],
      "progression": "Step-by-step resource flow."
    }}
  ],
  "win_conditions": [
    {{"win_type": "String", "key_cards": ["A"], "explanation": "String"}}
  ],
  "dead_weight_candidates": [
    {{"card_name": "string", "reason": "string"}}
  ]
}}
"""

def _enforce_dead_weight(parsed, isolated):
    isolated_set = set(isolated)
    kept, violations = [], []
    for d in parsed.get("dead_weight_candidates", []):
        if d.get("card_name") in isolated_set:
            kept.append(d)
        else:
            violations.append(d.get("card_name"))
    parsed["dead_weight_candidates"] = kept
    if violations:
        parsed.setdefault("diagnostics", {})["dead_weight_violations"] = violations
    return parsed

def generate_layer2b_engines(graph, commander_name, archetype="", model="qwen2.5:32b"):
    groups_text = _build_functional_groups(graph)
    bridges_text = _build_cross_group_bridges(graph)
    isolated = graph.get("candidate_isolated_cards", [])

    try:
        resp = ollama.chat(
            model=model, format="json",
            options={"temperature": 0, "num_ctx": 32768},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": _user_prompt(commander_name, groups_text, bridges_text, isolated)}
            ]
        )
        parsed = json.loads(resp["message"]["content"])
    except Exception as e:
        return {"_error": str(e), "functional_categories": [], "velocity_chains": []}

    parsed["diagnostics"] = {
        "groups_provided": len(groups_text.split("\n")),
        "bridges_provided": len(bridges_text.split("\n"))
    }
    return _enforce_dead_weight(parsed, isolated)