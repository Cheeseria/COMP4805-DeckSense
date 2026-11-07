# test1_layer2a.py
import json


def build_layer2a_graph(parsed_deck):
  """Layer 2A: Constructs a clean, deduplicated relational graph

  using abstract state-transition routing and economic complementarity
  without hardcoded card names or game rules.
  """
  nodes = []
  seen_names = set()

  # 1. Deduplicate Nodes
  for card in parsed_deck:
    if "Land" in card.get("type", ""):
      continue

    name = card.get("name")
    if name and name not in seen_names:
      seen_names.add(name)
      nodes.append({
          "name": name,
          "primary_role": card.get("primary_role", "Value Engine"),
          "summary": card.get("summary", ""),
          "text": card.get("text", ""),
          "cost": card.get("cost", ""),
          "type": card.get("type", ""),
          "hooks": card.get("synergy_hooks", []),
          "secondary_roles": card.get("secondary_role", []),
      })

  edges = []
  seen_edges = set()

  # 2. Iterate pairs with i < j to block self-loops and reverse duplicates
  for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
      card_a = nodes[i]
      card_b = nodes[j]

      shared_hooks = list(set(card_a["hooks"]) & set(card_b["hooks"]))
      is_connected = False
      relationship_reason = ""

      # Normalize hooks to lowercase strings for abstract matching
      hooks_a = [h.lower() for h in card_a["hooks"]]
      hooks_b = [h.lower() for h in card_b["hooks"]]
      
      hooks_a_str = " ".join(hooks_a)
      hooks_b_str = " ".join(hooks_b)

      # --- RULE 1: Exact Structural Hook Match ---
      if shared_hooks:
        is_connected = True
        relationship_reason = (
            f"Shared structural interaction hooks: {shared_hooks}"
        )

      # --- RULE 2: Economic Complementarity (Cost Reducers / Generators vs. Alternative Costs) ---
      is_producer_a = any(k in hooks_a_str for k in ["cost reducer", "mana generator", "ritual"])
      is_consumer_b = any(k in hooks_b_str for k in ["alternative cost", "additional cost", "buyback", "escape", "flashback", "blitz"])
      
      is_producer_b = any(k in hooks_b_str for k in ["cost reducer", "mana generator", "ritual"])
      is_consumer_a = any(k in hooks_a_str for k in ["alternative cost", "additional cost", "buyback", "escape", "flashback", "blitz"])

      if (is_producer_a and is_consumer_b) or (is_producer_b and is_consumer_a):
        is_connected = True
        relationship_reason = (
            "Economic State Flow: A resource/cost modifier complements an alternative or additional casting cost."
        )

      # --- RULE 3: Abstract State-Transition & Zone Routing ---
      # Matches zone changes/triggers (e.g., Battlefield -> Graveyard, Death triggers) 
      # with zone consumers/exits (e.g., Graveyard recursion, sacrifice outlets, triggers on death)
      zone_producers_a = any(k in hooks_a_str for k in ["zone change", "trigger: death", "sacrifice", "discard", "mill"])
      zone_consumers_b = any(k in hooks_b_str for k in ["graveyard", "return", "recurs", "cast from", "escape", "flashback"])

      zone_producers_b = any(k in hooks_b_str for k in ["zone change", "trigger: death", "sacrifice", "discard", "mill"])
      zone_consumers_a = any(k in hooks_a_str for k in ["graveyard", "return", "recurs", "cast from", "escape", "flashback"])

      if (zone_producers_a and zone_consumers_b) or (zone_producers_b and zone_consumers_a):
        is_connected = True
        relationship_reason = (
            "State-Transition Pipeline: Card A's zone movement or trigger complements Card B's graveyard/zone consumption."
        )

      if is_connected:
        # 4. Canonical Edge Check (Ensures unique edge representation)
        edge_key = tuple(sorted([card_a["name"], card_b["name"]]))
        edge_key_str = f"{edge_key[0]}|{edge_key[1]}"
        if edge_key_str not in seen_edges:
          seen_edges.add(edge_key_str)
          edges.append({
              "source": card_a["name"],
              "target": card_b["name"],
              "relationship_context": relationship_reason,
              "shared_hooks": shared_hooks,
          })

  return {
      "total_cards": len(nodes),
      "interaction_nodes": nodes,
      "interaction_edges": edges,
  }