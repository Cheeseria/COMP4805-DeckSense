# driver.py
"""
Driver: run ingest -> L1 -> L2a -> L2b -> L2c -> L3 -> L4 for one deck.
Safe to re-run; safe to run many decks.

Usage:
    python driver.py <archidekt_url> [archetype_hint]
"""
import hashlib
import json
import os
import sys
import time

import ingest
import layer1
import layer2a
import layer2b
import layer2c
import layer3
import layer4_primer

CACHE_ROOT = "cache"
os.makedirs(CACHE_ROOT, exist_ok=True)

CACHE_VERSION = "v2"
MODEL_L1 = "qwen2.5:32b"
MODEL_L2B = "qwen2.5:32b"


def _paths(deck_id):
    base = os.path.join(CACHE_ROOT, deck_id)
    return {
        "facts": f"{base}_facts.json",
        "l1":    f"{base}_l1.json",
        "l2a":   f"{base}_l2a.json",
        "l2b":   f"{base}_l2b.json",
        "l3":    f"{base}_l3.json",
        "l4":    f"{base}_l4_primer.md",
    }


def _meta(deck_id, url, model):
    return {
        "version": CACHE_VERSION,
        "deck_id": deck_id,
        "deck_url": url,
        "model": model,
        "written_at": time.time(),
    }


def _load(path, expected_meta):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return None
    meta = data.get("__meta") if isinstance(data, dict) else None
    if not meta or meta.get("version") != expected_meta["version"] \
            or meta.get("deck_id") != expected_meta["deck_id"] \
            or meta.get("model") != expected_meta["model"]:
        print(f"[driver] cache stale at {path}; ignoring")
        return None
    return data


def _save(path, payload, meta):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"__meta": meta, **payload}, f, indent=2)


def run(url, archetype=""):
    # Defensive: strip whitespace/newlines that may come from web textareas or CLI
    url = url.strip()
    print(f"[driver] deck URL: {url}")
    deck_id = url.rstrip("/").split("/")[-1].strip()

    # ---------- ingest ----------
    deck, commander_name, _ = ingest.parseArchiURL(url)
    if not commander_name:
        for c in deck:
            if getattr(c, "is_commander", False):
                commander_name = c.name
                break
    assert commander_name, "Could not identify commander"
    print(f"[driver] commander: {commander_name}  cards: {len(deck)}")

    # ---------- L1: facts ----------
    paths = _paths(deck_id)
    meta_l1 = _meta(deck_id, url, MODEL_L1)

    facts_cache = _load(paths["facts"], meta_l1)
    if facts_cache:
        facts_list = facts_cache["facts"]
        print(f"[driver] L1 facts: cache hit ({len(facts_list)})")
    else:
        facts_list = []
        for i, c in enumerate(deck, 1):
            try:
                facts_list.append(layer1.extract_card_facts(c))
            except Exception as e:
                print(f"[driver] extract_card_facts failed on {c.name}: {e}")
            if i % 10 == 0:
                print(f"[driver] facts {i}/{len(deck)}")
        _save(paths["facts"], {"facts": facts_list}, meta_l1)

    # ---------- L1: roles ----------
    l1_cache = _load(paths["l1"], meta_l1)
    if l1_cache:
        l1 = l1_cache["records"]
        print(f"[driver] L1 roles: cache hit ({len(l1)})")
    else:
        l1, l1_failures = [], []
        for i, facts in enumerate(facts_list, 1):
            rec = layer1.validate_card_role(facts, model=MODEL_L1)
            if "_error" in rec:
                l1_failures.append({"name": rec.get("name"), "error": rec["_error"]})
            l1.append(rec)
            if i % 5 == 0:
                print(f"[driver] roles {i}/{len(facts_list)}")
        _save(paths["l1"], {"records": l1, "failures": l1_failures}, meta_l1)
        print(f"[driver] L1 failures: {len(l1_failures)}")

    # ---------- L2a ----------
    l2a_cache = _load(paths["l2a"], meta_l1)
    if l2a_cache:
        graph = l2a_cache["graph"]
        print("[driver] L2a: cache hit")
    else:
        graph = layer2a.build_layer2a_graph(l1)
        _save(paths["l2a"], {"graph": graph}, meta_l1)
    print(f"[driver] L2a: nodes={len(graph['interaction_nodes'])} "
          f"edges={len(graph['interaction_edges'])} "
          f"cycles={len(graph['synergy_clusters'])} "
          f"isolated={len(graph['candidate_isolated_cards'])}")

    # ---------- L2b & L2c ----------
    meta_l2b = _meta(deck_id, url, MODEL_L2B)
    l2b_cache = _load(paths["l2b"], meta_l2b)
    if l2b_cache:
        l2b = l2b_cache["analysis"]
        print("[driver] L2b: cache hit")
    else:
        l2b_raw = layer2b.generate_layer2b_engines(
            graph, commander_name=commander_name,
            archetype=archetype, model=MODEL_L2B,
        )
        print("[driver] Running Layer 2c Fact Checker...")
        l2b = layer2c.fact_check_loops(l2b_raw, graph, model=MODEL_L2B)
        _save(paths["l2b"], {"analysis": l2b}, meta_l2b)

    # ---------- L3: Power Assessment ----------
    meta_l3 = _meta(deck_id, url, MODEL_L1)
    l3_cache = _load(paths["l3"], meta_l3)
    if l3_cache:
        l3 = l3_cache["assessment"]
        print("[driver] L3: cache hit")
    else:
        print("[driver] Running Layer 3 Power Assessment...")
        l3 = layer3.assess_power_level(graph, l2b, commander_name, model=MODEL_L1)
        _save(paths["l3"], {"assessment": l3}, meta_l3)
    print(f"[driver] L3: Est Bracket {l3.get('estimated_bracket')} | "
          f"Official Bracket {l3.get('official_bracket')} | "
          f"Win Turn: {l3.get('estimated_win_turn')}")

    # ---------- L4: Primer Generation ----------
    primer_path = paths["l4"]
    if os.path.exists(primer_path):
        print(f"[driver] L4 Primer: cache hit at {primer_path}")
    else:
        print("[driver] Running Layer 4 Primer Generation...")
        primer_text = layer4_primer.generate_primer(
            l2b_analysis=l2b,
            l3_assessment=l3,
            l1_data=l1,
            commander_name=commander_name
        )
        with open(primer_path, "w", encoding="utf-8") as f:
            f.write(primer_text)
        print(f"[driver] L4 Primer saved to {primer_path}")

    print("\n" + "="*40)
    print("PIPELINE COMPLETE")
    print("="*40)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python driver.py <archidekt_url> [archetype_hint]")
        sys.exit(1)
    archetype = sys.argv[2] if len(sys.argv) > 2 else ""
    run(sys.argv[1], archetype=archetype)