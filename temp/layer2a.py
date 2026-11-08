# layer2a.py
from collections import defaultdict

def _hook_kinds(hooks):
    return {h.get("kind", "") for h in hooks if isinstance(h, dict)}

def _edge_rules(a, b):
    ha, hb = a["hooks"], b["hooks"]
    ka, kb = _hook_kinds(ha), _hook_kinds(hb)
    rules = []

    # 1. Specific shared engines (e.g., two cards that both trigger on cast)
    SPECIFIC_SHARED = {"trigger:cast", "trigger:opponent_cast", "trigger:dies", "trigger:discard", "trigger:sacrifice", "recursion"}
    if (ka & kb) & SPECIFIC_SHARED:
        rules.append("shared_engine")

    # 2. Economic Linkages (e.g., a cost reducer and a flashback card)
    producers = {"cost_modifier", "cost_reduction", "mana_generator"}
    consumers = {"alternative cost", "additional cost", "cast trigger", "recursion"}
    if (ka & producers and kb & consumers) or (kb & producers and ka & consumers):
        rules.append("economic_link")

    # 3. Recursion Mana Loops (Reiterate + Storm-Kiln)
    if "recursion" in ka and ("mana_generator" in kb or "artifact token" in kb):
        rules.append("recursion_mana")
    if "recursion" in kb and ("mana_generator" in ka or "artifact token" in ka):
        rules.append("recursion_mana")

    return sorted(set(rules))

def build_layer2a_graph(layer1_records):
    seen = set()
    nodes = []
    for rec in layer1_records:
        if "_error" in rec: continue
        name = rec.get("name")
        if not name or name in seen: continue
        seen.add(name)
        nodes.append({
            "name": name, "primary_role": (rec.get("primary_role") or "value engine").strip().lower(),
            "summary": rec.get("summary", ""), "text": rec.get("oracle_text", ""),
            "cost": rec.get("mana_cost", ""), "cmc": rec.get("mana_value"),
            "type": rec.get("type", ""), "is_commander": bool(rec.get("is_commander", False)),
            "hooks": rec.get("synergy", []),
        })

    edges = []
    seen_edges = set()
    adj = defaultdict(set)
    
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)): 
            a, b = nodes[i], nodes[j]
            rules = _edge_rules(a, b)
            if not rules: continue
            
            key = tuple(sorted([a["name"], b["name"]]))
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({"source": a["name"], "target": b["name"], "relationship_types": rules, "weight": len(rules)})
                adj[a["name"]].add(b["name"])
                adj[b["name"]].add(a["name"])

    # Group into clusters (Connected Components)
    visited = set()
    clusters = []
    
    def dfs(node, current_cluster):
        visited.add(node)
        current_cluster.add(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                dfs(neighbor, current_cluster)

    for node in adj:
        if node not in visited:
            cluster = set()
            dfs(node, cluster)
            if len(cluster) > 1: 
                clusters.append(sorted(list(cluster)))

    clusters.sort(key=len, reverse=True)
    candidate_isolated_cards = [n["name"] for n in nodes if not adj[n["name"]]]

    return {
        "total_cards": len(nodes),
        "interaction_nodes": nodes,
        "interaction_edges": edges,
        "synergy_clusters": clusters, 
        "candidate_isolated_cards": candidate_isolated_cards,
    }