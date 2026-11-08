# layer2b.py
import json
import ollama

ALLOWED_PATH_TYPES = {"Velocity Chain", "Combat Win", "Validated Infinite Loop"}

def _flatten_edges(graph, max_edges=300): # Reduced back to 300 so the LLM doesn't choke
    edges = graph.get("interaction_edges", [])
    ranked = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)
    kept = ranked[:max_edges]
    dropped = len(ranked) - len(kept)

    node_map = {n["name"]: n for n in graph.get("interaction_nodes", [])}
    lines = []
    for e in kept:
        s, t = e["source"], e["target"]
        si, ti = node_map.get(s, {}), node_map.get(t, {})
        s_hooks = [h["kind"] for h in si.get("hooks", []) if h["kind"] in e["relationship_types"] or "trigger" in h["kind"] or "cost" in h["kind"]]
        t_hooks = [h["kind"] for h in ti.get("hooks", []) if h["kind"] in e["relationship_types"] or "trigger" in h["kind"] or "cost" in h["kind"]]
        s_str = ", ".join(set(s_hooks)) if s_hooks else "generic"
        t_str = ", ".join(set(t_hooks)) if t_hooks else "generic"
        lines.append(f"- '{s}' [{s_str}] <--> '{t}' [{t_str}] (w={e['weight']})")
    return "\n".join(lines), dropped

def _flatten_clusters(graph):
    clusters = graph.get("synergy_clusters", [])
    return "\n".join([f"Cluster {i} ({len(c)} cards): {', '.join(c)}" for i, c in enumerate(clusters, 1)])

# layer2b.py
# (Keep imports and other functions the same)

SYSTEM_PROMPT_TEMPLATE = """
You are a competitive Magic: The Gathering combo architect specializing in EDH.
Your job is to analyze the provided synergy graph and decklist to find actual win conditions and loops.

CRITICAL DEFINITION OF A LOOP:
A loop MUST physically generate the resources (mana, cards, tokens) required to execute the next iteration.
If Card A draws cards, but does not generate mana, and Card B costs mana, they do NOT loop. 
Do NOT list a sequence of synergistic spells as a "loop". 

REQUIRED ASSUMPTIONS:
If a loop requires a card OUTSIDE the loop to function (e.g., a cost reducer like Vadrik or Goblin Electromancer), you MUST list that card in `required_assumptions`. 
Example: "Requires Vadrik to have 3+ counters" or "Requires Goblin Electromancer on the battlefield".

LOOP VALIDATION RULES:
If you identify a loop, you MUST write out the mathematical proof:
  Step A (Input): The total mana required per iteration.
  Step B (Output): The total mana generated per iteration.
  Step C (Net): Output - Input >= 0.
"""

def _user_prompt(commander_name, edge_text, dropped, cluster_text, isolated, node_names):
    return f"""
Commander: {commander_name}

ALL AVAILABLE CARDS (Use this to check for missing cost reducers):
{json.dumps(sorted(node_names), indent=2)}

SYNERGY CLUSTERS (Groups of highly connected cards. Focus on these):
{cluster_text}

DENSE GRAPH EDGES ({dropped} omitted due to limit):
{edge_text}

CANDIDATE ISOLATED CARDS (Only these can be dead weight):
{json.dumps(isolated, indent=2)}

Return JSON:
{{
  "card_groups_and_intra_synergies": [
    {{"group_name": "string", "cards": ["A","B"], "intra_synergy_explanation": "string"}}
  ],
  "cross_group_synergies": [
    {{"bridged_groups": ["G1","G2"], "bridge_mechanism": "string"}}
  ],
  "validated_cycles": [
    {{"cards": ["A","B","C"], "path_type": "Velocity Chain | Combat Win | Validated Infinite Loop",
      "mechanical_validation": "Step A: ... Step B: ... Step C: ...", "required_assumptions": ["..."]}}
  ],
  "win_conditions_and_loops": [
    {{"path_type": "...", "key_cards": ["A","B"], "mechanical_validation": "string", "required_assumptions": ["..."]}}
  ],
  "dead_weight_candidates": [
    {{"card_name": "string", "reason": "string"}}
  ]
}}
"""

def generate_layer2b_engines(graph, commander_name, archetype="", model="qwen2.5:32b"):
    edge_text, dropped = _flatten_edges(graph)
    cluster_text = _flatten_clusters(graph)
    isolated = graph.get("candidate_isolated_cards", [])
    node_names = [n["name"] for n in graph.get("interaction_nodes", [])]

    try:
        resp = ollama.chat(model=model, format="json", options={"temperature": 0, "num_ctx": 16384},
            messages=[{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE}, 
                      {"role": "user", "content": _user_prompt(commander_name, edge_text, dropped, cluster_text, isolated, node_names)}])
        parsed = json.loads(resp["message"]["content"])
    except Exception as e:
        return {"_error": str(e), "validated_cycles": []}

    # Extract data for fact checker
    cited = set()
    for c in parsed.get("validated_cycles", []): cited.update(c.get("cards", []))
    for w in parsed.get("win_conditions_and_loops", []): cited.update(w.get("key_cards", []))
    cited_data = {}
    for n in graph.get("interaction_nodes", []):
        if n["name"] in cited:
            cited_data[n["name"]] = {
                "oracle_text": n["text"],
                "summary": n["summary"],
                "mana_value": n.get("cmc")
            }
    parsed["_cited_card_data"] = cited_data
    parsed["diagnostics"] = {"dropped_edges": dropped, "clusters_provided": len(graph.get("synergy_clusters", []))}
    return parsed