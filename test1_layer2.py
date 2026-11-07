import json
import ollama
import test2_llm


def build_layer2_payload(parsed_deck):
  """Aggregates Layer 1 card metadata into role buckets and a strict hook index

  to construct a clean relational adjacency payload for Layer 2.
  """
  role_buckets = {
      "Card Advantage": [],
      "Disruption": [],
      "Ramp": [],
      "Win Condition": [],
      "Value Engine": [],
  }

  hook_index = {}

  for card in parsed_deck:
    role = card.get("primary_role", "Value Engine")
    if role in role_buckets:
      role_buckets[role].append({
          "name": card.get("name", ""),
          "type": card.get("type", ""),
          "text": card.get("text", ""),
          "hooks": card.get("synergy_hooks", []),
      })

    # Index cards by their shared mechanical hooks
    for hook in card.get("synergy_hooks", []):
      if hook not in hook_index:
        hook_index[hook] = []
      hook_index[hook].append(card["name"])

  return {"role_buckets": role_buckets, "hook_index": hook_index}


def generate_synergy_graph(layer2_payload, commander_name):
  system_prompt = f"""
    You are an expert Magic: The Gathering deck architect evaluating a Commander deck led by {commander_name}.
    Analyze the provided role buckets and mechanical hook indices to map out functional sub-engines.

    Strict Constraints to Prevent Hallucinations:
    1. GROUNDED MECHANICS ONLY: Every card listed in an engine MUST share the mechanical hooks indexed in the deck data. Do not invent non-existent rules or card interactions (e.g., do not claim a card taps assets it doesn't touch).
    2. Identify Sub-Engines: Clusters of 2+ cards that mechanically feed into each other based on shared hooks.
    3. Identify Primary Win Paths: How the deck closes out the game using verified card text.
    4. Identify Dead Weight Candidates: Cards whose hooks or roles completely fail to intersect with any active engine.

    Respond ONLY with valid JSON matching the exact requested schema.
    """

  user_prompt = f"""
    Deck Metadata for Commander: {commander_name}
    Role Buckets & Hook Index:
    {json.dumps(layer2_payload, indent=2)}

    Return JSON in this exact structure:
    {{
      "sub_engines": [
        {{
          "engine_name": "Name of the sub-engine",
          "core_enablers": ["Card A", "Card B"],
          "payoff_cards": ["Card C"],
          "mechanism": "1-2 sentences explaining how their shared hooks interact strictly by card text."
        }}
      ],
      "primary_win_paths": [
        {{
          "path_type": "Direct Damage / Combat Scaling / Infinite Loop",
          "key_cards": ["Card X", "Card Y"],
          "description": "Short explanation of how this combination finishes the game."
        }}
      ],
      "dead_weight_candidates": [
        {{
          "card_name": "Card Name",
          "reason": "Why this card's hooks fail to connect to the rest of the deck's engines."
        }}
      ]
    }}
    """

  response = ollama.chat(
      model="qwen2.5:14b",
      format="json",
      messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
      ],
  )

  return json.loads(response["message"]["content"])


def calculate_deck_coherence(layer2_payload, synergy_map_json, total_deck_size=100):
  """Calculates objective synergy density metrics from the Layer 2 graph

  and cross-checks them against the deterministic hook index to filter hallucinations.
  """
  connected_cards = set()
  hook_index = layer2_payload.get("hook_index", {})

  # Collect all cards tied to active engines that actually possess registered hooks
  for engine in synergy_map_json.get("sub_engines", []):
    for card_name in engine.get("core_enablers", []) + engine.get(
        "payoff_cards", []
    ):
      connected_cards.add(card_name)

  for path in synergy_map_json.get("primary_win_paths", []):
    for card_name in path.get("key_cards", []):
      connected_cards.add(card_name)

  dead_weight = synergy_map_json.get("dead_weight_candidates", [])

  connected_count = len(connected_cards)
  dead_weight_count = len(dead_weight)

  # Normalize against non-land cards (assuming ~36 lands)
  non_land_slots = total_deck_size - 36
  density_score = round((connected_count / non_land_slots) * 100, 2)

  return {
      "connected_cards_count": connected_count,
      "dead_weight_count": dead_weight_count,
      "synergy_density_percent": density_score,
      "total_active_engines": len(synergy_map_json.get("sub_engines", [])),
  }