# layer2a.py
from collections import defaultdict


def _get_domains(card):
    return {d.strip().lower() for d in card.get("domains", [])}


def _augment_domains(rec):
    """Deterministic floor: a card with a mana cost requires mana.
    Not a combo rule — a definitional truth about mana costs."""
    domains = list(rec.get("domains", []))
    cmc = rec.get("mana_value")
    if cmc is not None and cmc > 0:
        already = any(
            d.lower().replace("requires:", "").strip() == "mana"
            for d in domains
        )
        if not already:
            domains.append("Requires: Mana")
    return domains


def _edge_rules(a, b):
    da, db = _get_domains(a), _get_domains(b)
    a_produces = {d.replace("produces: ", "").strip() for d in da if d.startswith("produces:")}
    a_requires = {d.replace("requires: ", "").strip() for d in da if d.startswith("requires:")}
    b_produces = {d.replace("produces: ", "").strip() for d in db if d.startswith("produces:")}
    b_requires = {d.replace("requires: ", "").strip() for d in db if d.startswith("requires:")}

    rules = []
    if a_produces & b_requires:
        rules.append("feeds_target")
    if b_produces & a_requires:
        rules.append("feeds_source")
    return rules


def build_layer2a_graph(layer1_records):
    seen = set()
    nodes = []
    for rec in layer1_records:
        if "_error" in rec:
            continue
        name = rec.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        nodes.append({
            "name": name,
            "primary_role": (rec.get("primary_role") or "value engine").strip().lower(),
            "secondary_roles": [s.get("role") for s in (rec.get("secondary_roles") or [])],
            "summary": rec.get("summary", ""),
            "text": rec.get("oracle_text", ""),
            "cost": rec.get("mana_cost", ""),
            "cmc": rec.get("mana_value"),
            "type": rec.get("type", ""),
            "keywords": rec.get("keywords", []),
            "is_commander": bool(rec.get("is_commander", False)),
            "user_categories": rec.get("user_categories", []),
            "mechanisms": rec.get("mechanisms", []),
            "domains": _augment_domains(rec),
        })

    edges = []
    seen_edges = set()
    adj = defaultdict(set)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            rules = _edge_rules(a, b)
            if not rules:
                continue
            key = tuple(sorted([a["name"], b["name"]]))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "source": a["name"],
                "target": b["name"],
                "relationship_types": rules,
                "weight": len(rules),
            })
            adj[a["name"]].add(b["name"])
            adj[b["name"]].add(a["name"])

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