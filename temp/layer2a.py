# layer2a.py
from collections import defaultdict

def _get_domains(card):
    return {d.strip().lower() for d in card.get("domains", [])}

def _edge_rules(a, b):
    da, db = _get_domains(a), _get_domains(b)
    a_produces = {d.replace("produces: ", "").strip() for d in da if d.startswith("produces:")}
    a_requires = {d.replace("requires: ", "").strip() for d in da if d.startswith("requires:")}
    b_produces = {d.replace("produces: ", "").strip() for d in db if d.startswith("produces:")}
    b_requires = {d.replace("requires: ", "").strip() for d in db if d.startswith("requires:")}

    rules = []
    
    # Check for specific overlaps (excluding generic 'mana')
    a_prod_spec = a_produces - {"mana"}
    a_req_spec = a_requires - {"mana"}
    b_prod_spec = b_produces - {"mana"}
    b_req_spec = b_requires - {"mana"}

    if a_prod_spec & b_req_spec:
        rules.append("specific_link")
    if b_prod_spec & a_req_spec:
        rules.append("specific_link")

    # Check for mana-only overlaps
    if not rules:
        if a_produces & b_requires or b_produces & a_requires:
            rules.append("mana_link")

    return rules

def build_layer2a_graph(layer1_records):
    seen = set()
    nodes = []
    for rec in layer1_records:
        if "_error" in rec: continue
        name = rec.get("name")
        if not name or name in seen: continue
        seen.add(name)
        
        # Augment domains deterministically (ensure spells require mana)
        domains = list(rec.get("domains", []))
        if rec.get("mana_value") and rec.get("mana_value") > 0:
            if not any(d.lower() == "requires: mana" for d in domains):
                domains.append("Requires: Mana")
                
        nodes.append({
            "name": name,
            "primary_role": (rec.get("primary_role") or "value engine").strip().lower(),
            "summary": rec.get("summary", ""),
            "text": rec.get("oracle_text", ""),
            "cost": rec.get("mana_cost", ""),
            "cmc": rec.get("mana_value"),
            "type": rec.get("type", ""),
            "is_commander": bool(rec.get("is_commander", False)),
            "mechanisms": rec.get("mechanisms", []),
            "domains": domains,
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
            if key in seen_edges: continue
            seen_edges.add(key)
            
            edges.append({
                "source": a["name"],
                "target": b["name"],
                "relationship_types": rules,
                "weight": len(rules),
            })
            
            # CRITICAL FIX: Do NOT cluster cards if their only link is mana.
            # Mana is universal; clustering on it collapses the graph.
            if "specific_link" in rules:
                adj[a["name"]].add(b["name"])
                adj[b["name"]].add(a["name"])

    # Cluster based ONLY on specific overlaps
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
    
    # Isolated cards: cards with NO edges at all (not even mana links)
    all_connected = set()
    for e in edges:
        all_connected.add(e["source"])
        all_connected.add(e["target"])
    candidate_isolated_cards = [n["name"] for n in nodes if n["name"] not in all_connected]

    return {
        "total_cards": len(nodes),
        "interaction_nodes": nodes,
        "interaction_edges": edges,
        "synergy_clusters": clusters,
        "candidate_isolated_cards": candidate_isolated_cards,
    }