# layer4_primer.py
import json
import ollama


SYSTEM_PROMPT_PART1 = """
You are an expert Magic: The Gathering teacher explaining a Commander deck to a beginner.
You are writing PART 1 of a 2-part primer. PART 1 covers the deck profile, the functional engines, and the win conditions.

CRITICAL RULES:
1. You MUST read the exact ORACLE TEXT provided for each card. Do NOT invent abilities or infer functions from a card's name.
2. Clearly differentiate between the "Estimated Bracket" (strategy-based) and "Official Bracket" (WotC Game Changer rules).
3. If any Game Changers are in the deck, list them explicitly.
4. Do NOT copy phrases from these instructions. Reason about each answer based on the actual card data provided.

Output EXACTLY these three markdown headings in this order, with the subsections described. Do NOT add extra sections. Do NOT rename headings.

## 1. Executive Summary & Deck Profile

Reason first about what this deck is doing. Then write:
- **Archetype & Win Style:** Classify the deck based on how it actually wins, using evidence from the win conditions and velocity chains. Be specific (e.g., "storm combo," "midrange value," "landfall aggro").
- **Power Level / Bracket:** State the Estimated Bracket, Official WotC Bracket, Estimated Win Turn, and any Game Changers found. If the two brackets differ, explain why in one sentence.
- **Core Philosophy:** Answer "What is this deck trying to achieve, and at what speed?" in 2-3 sentences. Ground the answer in the specific engines and win conditions identified below, not generic strategy language.

## 2. Key Card Categorization & Functional Roles

Categorize cards by what they ACTUALLY DO according to their oracle text, NOT by where they appear in the graph. A counterspell is interaction, not an engine. A ritual is mana acceleration, not a win condition.
- **The Engine (Enablers):** Choose the 5-8 cards that actually generate resources or unlock plays. For each, one sentence: what resource it generates and what it costs.
- **Synergy-Based Plays / Win Conditions:** Choose the 3-6 cards that actually end the game or close out the loop. For each, one sentence: what it does and how it contributes to winning.
- **The Interaction Package:** Choose the 3-6 cards that protect or disrupt. For each, one sentence: what it interacts with.

## 3. Win Conditions & Line Execution

Before writing, identify the deck's ACTUAL win loop by looking at the velocity chains and the specific cards involved. Then:
- **Primary Line(s):** Walk through the sequence step by step. Name the specific cards in order. Explain what each card does mechanically using the oracle text. If the line depends on a cost reducer or a specific game state, say so.
- **Prerequisites:** List the specific game state required to execute the primary line. For each prerequisite, state what it enables mechanically (e.g., "Commander has 4+ power, which makes buyback spells free to recast"). Do NOT list prerequisites that aren't mechanistically justified by the cards.
- **Backup Win Plans:** Describe one or two alternative lines that use different cards. Explain when you would pivot to them.
"""


SYSTEM_PROMPT_PART2 = """
You are an expert Magic: The Gathering teacher explaining a Commander deck to a beginner.
You are writing PART 2 of a 2-part primer. PART 2 covers turn sequencing, mulligan strategy, and matchups.

CRITICAL RULES:
1. You MUST read the exact ORACLE TEXT provided for each card. Do NOT invent abilities.
2. Do NOT copy phrases from these instructions. Every answer must be derived from the actual cards in this deck.
3. You MUST output EXACTLY these three markdown headings in this order. Do NOT add extra sections like "Common Mistakes" or "Tips".

## 4. Turn-by-Turn Gameplan

- **Early Game (Turns 1-3):** Look at the deck's mana curve and identify which cards are playable on turns 1-3. Describe the plays you want to make by turn 3. Explicitly include playing Lands as part of the plan.
- **Mid-to-Late Game Execution:** Identify the turn the deck typically transitions from setup to winning. Describe what that transition looks like in practice (which cards signal "it's time to go for the win"). Use the Estimated Win Turn from Layer 3 as your anchor.

## 5. Sample Opening Hand & Mulligan Guidelines

Before writing the sample hand, do this:
STEP 1: Look at the deck's mana curve. Count how many lands and how many 1-2 CMC ramp/draw pieces the deck actually contains.
STEP 2: Based on the actual curve, decide what a realistic keep looks like. A storm deck with 33 two-drops wants 1-2 lands and 2-3 cheap cantrips. A landfall deck wants 3-4 lands and 1-2 land-ramp pieces.
STEP 3: Pick EXACTLY 7 real cards from the decklist that match this profile. The hand MUST include at least 1 land and at least 1 cheap play. Do not invent cards.
STEP 4: Verify your hand against your own criteria. If the hand doesn't meet the criteria you wrote, pick a different hand.

Then write:
- **Keep Criteria:** State the criteria you derived in Steps 1-2. Ground it in the actual curve.
- **Annotated Sample Hand:** List exactly 7 cards from the decklist. Format each as "N. [Card Name] - [one sentence on why it's in the hand]". State whether the decision is KEEP or MULLIGAN. Explain in 2-3 sentences why the hand meets (or fails) the criteria.

## 6. Threat Assessment & Strategic Context

- **Window Opportunities:** When is this deck vulnerable? When should it strike? Base your answer on the deck's speed (from Layer 3's estimated win turn) and the shape of its combo. Explain WHY those windows exist.
- **Silver Bullets & Hard Counters:** Identify 2-3 opposing strategies or specific card types that would shut down this deck's primary line, and describe how the deck can play around them. Use the interaction package to ground your answer.
"""


def _build_context(l2b_analysis, l3_assessment, l1_data, commander_name):
    """Shared context builder for both LLM calls."""
    mentioned_cards = set()
    mentioned_cards.add(commander_name)
    for cat in l2b_analysis.get("functional_categories", []):
        mentioned_cards.update(cat.get("key_cards", []))
    for chain in l2b_analysis.get("velocity_chains", []):
        mentioned_cards.update(chain.get("key_cards", []))
    for win in l2b_analysis.get("win_conditions", []):
        mentioned_cards.update(win.get("key_cards", []))

    key_cards_text = ""
    for card in l1_data:
        if card["name"] in mentioned_cards:
            text = card.get("oracle_text", "").replace("\n", " ")
            key_cards_text += f"- **{card['name']}**: {text}\n"

    # Include the FULL decklist so the LLM can pick a real sample hand
    full_decklist = ", ".join([card["name"] for card in l1_data])

    l3_text = "Not provided."
    if l3_assessment:
        gc_list = ", ".join(l3_assessment.get("_stats_used", {}).get("game_changer_list", []))
        l3_text = f"""
        Estimated Power Bracket: {l3_assessment.get('estimated_bracket')}
        Official WOTC Bracket: {l3_assessment.get('official_bracket')}
        Growth Model: {l3_assessment.get('growth_model')}
        Game Changers Found: {gc_list if gc_list else 'None'}
        Bracket Justification: {l3_assessment.get('bracket_justification')}
        Estimated Win Turn: {l3_assessment.get('estimated_win_turn')}
        Playstyle: {l3_assessment.get('playstyle_summary')}
        """

    return f"""
    Commander: {commander_name}

    LAYER 3 ASSESSMENT (Power Level & Speed):
    {l3_text}

    KEY ENGINES (Use this EXACT text to explain the combos):
    {key_cards_text}

    FULL DECKLIST (For sample hand selection):
    {full_decklist}

    STRATEGY HINTS:
    - Deck Identity: {l2b_analysis.get('deck_identity', '')}
    - Velocity Chains: {json.dumps(l2b_analysis.get('velocity_chains', []), indent=2)}
    """


def generate_primer(l2b_analysis, l3_assessment, l1_data, commander_name, model="qwen2.5:32b"):
    context = _build_context(l2b_analysis, l3_assessment, l1_data, commander_name)

    print("[layer4] Generating Part 1 (Sections 1-3)...")
    response1 = ollama.chat(
        model=model,
        options={"temperature": 0.1, "num_ctx": 16384},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_PART1},
            {"role": "user", "content": context + "\n\nWrite Sections 1-3 only. Stop after Section 3."}
        ]
    )
    part1 = response1["message"]["content"].strip()

    print("[layer4] Generating Part 2 (Sections 4-6)...")
    response2 = ollama.chat(
        model=model,
        options={"temperature": 0.1, "num_ctx": 16384},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_PART2},
            {"role": "user", "content": context + "\n\nWrite Sections 4-6 only. Start directly at ## 4."}
        ]
    )
    part2 = response2["message"]["content"].strip()

    full_primer = part1 + "\n\n" + part2
    print(f"[layer4] Total primer length: {len(full_primer)} chars")
    return full_primer