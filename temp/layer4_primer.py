# layer4_primer.py
import json
import ollama

SYSTEM_PROMPT = """
You are an expert Magic: The Gathering teacher explaining a Commander deck to a beginner.
Your goal is to write a primer that uses short sentences, defines all jargon, and avoids overwhelming the reader.

CRITICAL RULES:
1. You MUST read the exact ORACLE TEXT provided for each card. Do NOT invent abilities from memory.
2. Clearly differentiate between the "Estimated Bracket" (based on strategy) and "Official Bracket" (based on Game Changers).
3. Mention if any Game Changers are present in the deck.

Follow this exact structure:
1. Executive Summary & Deck Profile (Include both brackets and Win Turn)
2. Key Card Categorization (The Engines)
3. Win Conditions & Line Execution
4. Turn by Turn Gameplan (Include playing Lands!)
5. Sample Opening Hand (7 cards in hand, include 2-3 Lands and explain why it's a KEEP)

Constraints:
- Define jargon (explain what "Storm", "Buyback", "Ramp", and "Game Changer" mean).
- Keep the reading level accessible (short sentences, avoid dense paragraphs).
"""

def generate_primer(l2b_analysis, l3_assessment, l1_data, commander_name):
    # Extract exact text for mentioned key cards
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

    # Format Layer 3 Data
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

    prompt = f"""
    Commander: {commander_name}
    
    LAYER 3 ASSESSMENT (Power Level & Speed):
    {l3_text}
    
    KEY ENGINES (Use this EXACT text to explain the combos):
    {key_cards_text}
    
    STRATEGY HINTS:
    - Deck Identity: {l2b_analysis.get('deck_identity', '')}
    - Velocity Chains: {json.dumps(l2b_analysis.get('velocity_chains', []), indent=2)}
    
    Write the primer. Ensure the Sample Opening Hand includes lands.
    """
    
    response = ollama.chat(
        model="qwen2.5:32b", 
        options={"temperature": 0.1},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )
    return response["message"]["content"]