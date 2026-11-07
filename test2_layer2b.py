import json
import ollama


def load_layer2a_cache(filepath="layer2a_cache_2.json"):
    """Loads the Layer 2A interaction graph from the local cache file."""
    with open(filepath, "r") as f:
        cache_data = json.load(f)
    return cache_data

def flatten_graph_edges(cache_data, max_edges=150):
    """Flattens edge arrays into concise single-line narrative strings containing

    types and full Layer 1 summaries to prevent hallucinations.
    """
    flattened_lines = []
    edges = cache_data.get("interaction_edges", [])
    
    node_map = {
        node["name"]: {
            "type": node.get("type", "Unknown"),
            "summary": node.get("summary", "No summary"),
            "primary_role": node.get("primary_role", "Unknown")
        }
        for node in cache_data.get("interaction_nodes", [])
    }

    for edge in edges[:max_edges]:
        source = edge.get("source")
        target = edge.get("target")
        context = edge.get("relationship_context", "interacts with")
        shared_hooks = edge.get("shared_hooks", [])

        s_info = node_map.get(source, {"type": "Unknown", "summary": "", "primary_role": ""})
        t_info = node_map.get(target, {"type": "Unknown", "summary": "", "primary_role": ""})

        hook_str = f" [Hooks: {', '.join(shared_hooks)}]" if shared_hooks else ""
        
        # PASS THE FULL SUMMARY WITHOUT [:70] TRUNCATION
        flattened_lines.append(
            f"- '{source}' ({s_info['type']}): \"{s_info['summary']}\" "
            f"--> '{target}' ({t_info['type']}): \"{t_info['summary']}\" "
            f"via {{{context}}}{hook_str}"
        )

    return "\n".join(flattened_lines)

def generate_layer2b_engines(cache_data, commander_name="Vadrik, Astral Archmage"):
    # 1. Flatten the edges into explicit narrative lines so attention heads don't drop targets
    flattened_edge_text = flatten_graph_edges(cache_data, max_edges=150)
    
    # 2. Extract node summaries to give the model context of available card pool
    nodes_summary = [node["name"] for node in cache_data.get("interaction_nodes", [])]

    system_prompt = f"""
    You are a competitive Magic: The Gathering combo architect and rules expert specializing in Izzet Spellslinger/Storm lists led by {commander_name}.

    Your objective is to uncover rigorous, mechanical win conditions and infinite loops by analyzing economic conversion rates, cost reduction math, and buyback mechanics.

    CORE STRATEGIC ARCHITECTURE TO TRACE:
    1. RAMP -> PLAYING THE GAME: Mana generation funds disruption, draw spells, or just spells in general, and are highly relevant to playing the game.
    2. RAMP -> TUTORS -> COMBO: Fast mana, card draw, and tutors (cards that search for cards in libraries) are important to assemble win conditions.
    3. COST REDUCTION MATH: When cost reduction (X) meets spell mana values or buyback costs, net-positive mana loops emerge.

    MANDATORY LOOP VALIDATION RULES FOR LAYER 2B:
    To validate an infinite loop or high-velocity win line, you must explicitly write out the arithmetic step-by-step:
    - Step A (Input Cost): Total mana/resources required to cast the card and its buyback/escape/recurrent cost (accounting for active cost reducers).
    - Step B (Output Generation): Total mana or cards generated upon resolution.
    - Step C (Net Balance): Output - Input >= 0 (must be net-neutral or net-positive to qualify as a "Validated Infinite Loop").

    WIN EXPLANATIONS:
    - Combat Win: This win condition arises when the deck is able to capitalise on a strong boardstate, generally some spell or ability after generating a large number of tokens, creatures, power, or general statlines that accumulate to a large amount of damage dealt during the combat phase.
    - Velocity Chain: This win condition arises when a non-deterministic loop (i.e. a nonguaranteed infinite loop, typically occuring within decks with a high enough synergy, a high enough value generation, and a high enough card advantage that all interact with each other), causing a noncombat win state, such as a large amount of noncombat damage, forcing a state based lose condition (such as reducing the number of cards in the enemy library to 0), creating a large amount of creatures that usually are enough to kill, etc.
    - Infinite Loop: This win condition arises when a set of cards produces the resources necessary to replay the loop, such as enough counters, mana, etc. Each loop typically takes 2 to 10 steps of casting spells or using/triggering abilities each, so for each potential loop, consider multiple steps. The loop is considered a Winning Infinite Combo when the positive feedback loop results in the invocation of a loss condition for the opponent, e.g. reducing their life total infinitely by noncombat damage, creating a creature that can attack for infinite damage, creating infinite creatures that can attack, reducing the number of cards in all libraries by an infinite amount, etc.
    
    Decks are able to have multiple win conditions of each variety, or have none at all, and it is your job to identify whether one exists, and of what variety the win condition is.

    MANDATORY COVERAGE RULE:
    You must actively distribute and reference as many unique cards from the "Available Card Nodes in Pool" list as possible across your groups and combo lines. Do not restrict your analysis to just a few cards.
    Respond ONLY with valid JSON matching the requested schema. No conversational filler.
    """

    user_prompt = f"""
    Commander / Leader: {commander_name}
    
    EXPLICIT EDGE FLOWS (Source -> Target Mapping):
    {flattened_edge_text}

    Available Card Nodes in Pool:
    {json.dumps(nodes_summary, indent=2)}

    Return JSON strictly matching this structure, each group can have multiple entries:
    {{
      "card_groups_and_intra_synergies": [
        {{
          "group_name": "Dynamic Functional Group Name",
          "cards": ["Card A", "Card B"],
          "intra_synergy_explanation": "Detailed explanation of how these specific cards mechanically interact via hooks or state flows, verified by card types."
        }}
      ],
      "cross_group_synergies": [
        {{
          "bridged_groups": ["Group A", "Group B"],
          "bridge_mechanism": "How these two distinct functional groups connect based on graph edges, citing specific card examples."
        }}
      ],
      "win_conditions_and_loops": [
        {{
          "path_type": "Velocity Chain / Combat Win / Validated Infinite Loop",
          "key_cards": ["X", "Y"],
          "mechanical_validation": "Step-by-step logic proving how these cards transition the deck to a winning board state or a win, strictly following the symbolic loop validation rule and type verification."
        }}
      ],
      "dead_weight_candidates": [
        {{
          "card_name": "Card Name",
          "reason": "Rigorous justification explaining why this card's structural hooks fail to integrate into any dynamic engine."
        }}
      ]
    }}
    """

    response = ollama.chat(
        model="qwen2.5:32b",
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return json.loads(response["message"]["content"])
