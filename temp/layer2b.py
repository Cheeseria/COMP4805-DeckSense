# layer2b.py
import json
import ollama

ALLOWED_PATH_TYPES = {"Velocity Chain", "Combat Win", "Validated Infinite Loop"}


def _cluster_of(graph):
    """Map card name -> cluster index. Cards not in any cluster get -1."""
    mapping = {}
    for i, cluster in enumerate(graph.get("synergy_clusters", [])):
        for name in cluster:
            mapping[name] = i
    return mapping


def _score_edge(e, node_map, cluster_map):
    """Higher = more likely to matter for loop-finding.

    Priority order:
      1. Cross-cluster edges (the bridges where loops form)
      2. Weight (number of independent domain overlaps)
      3. Loop-relevance bonus (either endpoint has loop-relevant mechanisms)
    """
    LOOP_MECHS = {
        "cost reduction", "spell copy", "buyback", "flashback", "escape",
        "magecraft", "cast trigger", "graveyard cast", "mana generation",
        "recursion", "card draw", "card return to hand"
    }

    def hits(name):
        mechs = {m.lower() for m in node_map.get(name, {}).get("mechanisms", [])}
        return bool(mechs & LOOP_MECHS)

    w = e.get("weight", 0)
    bonus = (1 if hits(e["source"]) else 0) + (1 if hits(e["target"]) else 0)

    s_cluster = cluster_map.get(e["source"], -1)
    t_cluster = cluster_map.get(e["target"], -1)
    crosses = 1 if (s_cluster != -1 and t_cluster != -1 and s_cluster != t_cluster) else 0

    return (crosses, w, bonus)


def _flatten_edges(graph, max_edges=200):
    edges = graph.get("interaction_edges", [])
    node_map = {n["name"]: n for n in graph.get("interaction_nodes", [])}
    cluster_map = _cluster_of(graph)

    ranked = sorted(edges, key=lambda e: _score_edge(e, node_map, cluster_map), reverse=True)
    kept = ranked[:max_edges]
    dropped = len(ranked) - len(kept)

    lines = []
    for e in kept:
        s, t = e["source"], e["target"]
        si, ti = node_map.get(s, {}), node_map.get(t, {})
        s_doms = si.get("domains", [])[:4]
        t_doms = ti.get("domains", [])[:4]
        s_str = " | ".join(s_doms) if s_doms else "(no domains)"
        t_str = " | ".join(t_doms) if t_doms else "(no domains)"
        rels = ", ".join(e.get("relationship_types", []))
        lines.append(f"- '{s}' [{s_str}] --({rels}, w={e['weight']})--> '{t}' [{t_str}]")
    return "\n".join(lines), dropped


def _flatten_cross_cluster(graph, max_edges=100):
    """Separately surface the cross-cluster bridges — the edges where loops live."""
    edges = graph.get("interaction_edges", [])
    node_map = {n["name"]: n for n in graph.get("interaction_nodes", [])}
    cluster_map = _cluster_of(graph)

    cross = [e for e in edges
             if cluster_map.get(e["source"], -1) != -1
             and cluster_map.get(e["target"], -1) != -1
             and cluster_map[e["source"]] != cluster_map[e["target"]]]

    cross.sort(key=lambda e: e.get("weight", 0), reverse=True)
    kept = cross[:max_edges]

    lines = []
    for e in kept:
        s, t = e["source"], e["target"]
        si, ti = node_map.get(s, {}), node_map.get(t, {})
        s_doms = si.get("domains", [])[:3]
        t_doms = ti.get("domains", [])[:3]
        s_str = " | ".join(s_doms) if s_doms else "(no domains)"
        t_str = " | ".join(t_doms) if t_doms else "(no domains)"
        rels = ", ".join(e.get("relationship_types", []))
        c_s = cluster_map.get(s)
        c_t = cluster_map.get(t)
        lines.append(f"- [{c_s}→{c_t}] '{s}' [{s_str}] --({rels}, w={e['weight']})--> '{t}' [{t_str}]")
    return "\n".join(lines), len(cross) - len(kept)


def _flatten_cluster_roles(graph):
    """Summarize what each cluster is functionally."""
    clusters = graph.get("synergy_clusters", [])
    nodes = {n["name"]: n for n in graph.get("interaction_nodes", [])}
    lines = []
    for i, cluster in enumerate(clusters):
        mechs = {}
        for name in cluster:
            for m in nodes.get(name, {}).get("mechanisms", []):
                mechs[m.lower()] = mechs.get(m.lower(), 0) + 1
        top_mechs = sorted(mechs.items(), key=lambda x: -x[1])[:3]
        mech_summary = ", ".join(f"{m}" for m, _ in top_mechs) if top_mechs else "misc"
        lines.append(f"  Cluster {i} ({len(cluster)} cards) — dominant roles: {mech_summary}")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """
You are a competitive Magic: The Gathering combo architect specializing in EDH.
Your job is to find actual win conditions and loops in the provided decklist.

CRITICAL DEFINITION OF A LOOP:
A loop is a SPECIFIC 2-4 card cycle. It must regenerate the resources consumed
to start the next iteration. If a resource is consumed and not regenerated, the
sequence is a synergistic play, NOT a loop.

A "loop" containing 20+ cards is NOT a loop. Reject such groupings.

STEP 1 — LOOPS CROSS FUNCTIONAL BOUNDARIES:
A loop is not a group of similar cards. Cards that share mechanisms (all
buyback, all mana rocks) are synergistic but do not loop with each other,
because they all consume or produce the SAME resources. A loop forms when a
card in one functional group (e.g. "consumes mana") connects to a card in a
different functional group (e.g. "produces mana"), and their combined cycle
regenerates what each other consumes.

Every loop must contain at least one CROSS-CLUSTER EDGE. If all cards in a
candidate loop are in the same cluster, it is NOT a loop — it is an
intra-cluster synergy that fails the regeneration test.

STEP 2 — ENUMERATE CROSS-CLUSTER EDGES:
Read every edge in the CROSS-CLUSTER BRIDGES list. For each bridge, ask:
"Does Card A consume a resource that Card B produces, AND does Card B
consume a resource that Card A produces?"
- Both directions → loop candidate.
- One direction only → combo line, not a loop.

STEP 2b — EXPAND TO 3-4 CARDS:
If a bridge pair consumes but does not fully regenerate, look for a third
card (from any cluster) that regenerates the missing resource. Regeneration
mechanisms are NOT limited to buyback/flashback — reusable activated
abilities, untap effects, cost reducers, replacement effects, trigger loops,
and static resource-conversion effects are all valid.

STEP 3 — VALIDATE WITH MATH:
For each surviving candidate, write out:
  Step A (Input): resources consumed per iteration (mana, cards, life, tapped permanents).
  Step B (Output): resources produced or regenerated per iteration.
  Step C (Net): Output - Input. Only Step C >= 0 qualifies as a Validated Infinite Loop.

REQUIRED ASSUMPTIONS:
If the loop requires an external enabler (cost reducer, mana doubler, etc.),
name it explicitly in required_assumptions. Do not write "sufficient mana"
or "a commander in play."

STRICT DEAD WEIGHT RULE:
Only list a card in dead_weight_candidates if it appears in CANDIDATE
ISOLATED CARDS.
"""


def _user_prompt(commander_name, edge_text, dropped, cross_text, cross_dropped,
                 cluster_roles, isolated, node_names):
    return f"""
Commander: {commander_name}

ALL AVAILABLE CARDS:
{json.dumps(sorted(node_names), indent=2)}

CLUSTER ROLES (functional summary of each synergy cluster):
{cluster_roles}

CROSS-CLUSTER BRIDGES (edges connecting different clusters — THESE ARE WHERE LOOPS FORM; {cross_dropped} lower-weight bridges omitted):
{cross_text}

DENSE GRAPH EDGES (full ranked edge list; {dropped} lower-priority edges omitted):
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
    edge_text, dropped = _flatten_edges(graph, max_edges=200)
    cross_text, cross_dropped = _flatten_cross_cluster(graph, max_edges=100)
    cluster_roles = _flatten_cluster_roles(graph)
    isolated = graph.get("candidate_isolated_cards", [])
    node_names = [n["name"] for n in graph.get("interaction_nodes", [])]

    try:
        resp = ollama.chat(
            model=model, format="json",
            options={"temperature": 0, "num_ctx": 32768},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": _user_prompt(
                    commander_name, edge_text, dropped, cross_text,
                    cross_dropped, cluster_roles, isolated, node_names
                )}
            ]
        )
        parsed = json.loads(resp["message"]["content"])
    except Exception as e:
        return {"_error": str(e), "validated_cycles": [], "dead_weight_candidates": []}

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
    parsed["diagnostics"] = {
        "dropped_edges": dropped,
        "cross_cluster_edges_dropped": cross_dropped,
        "clusters_provided": len(graph.get("synergy_clusters", [])),
    }
    return _enforce_dead_weight(parsed, isolated)