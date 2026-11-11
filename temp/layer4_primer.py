# layer4_primer.py
import json
import ollama

SYSTEM_PROMPT = """
You are an expert Magic: The Gathering teacher explaining a Commander deck to a beginner.
Your goal is to write a primer that uses short sentences, defines all jargon, and avoids overwhelming the reader.

CRITICAL RULE FOR ACCURACY:
You MUST use the exact ORACLE TEXT provided in the "Key Engines" section below. 
DO NOT rely on your memory of these cards. 
- If the provided text says "Buyback", explain Buyback.
- If the provided text says "Create a Treasure token", explain Treasure tokens.
- If you do not see "Draw a card" in the text, DO NOT claim it draws a card.

Follow this exact structure:
1. Executive Summary & Deck Profile (Include the Power Bracket and Win Turn)
2. Key Card Categorization (The Engines)
3. Win Conditions & Line Execution (Explain the combo loop!)
4. Turn by Turn Gameplan
5. Sample Opening Hand (Invent a realistic 7-card hand from the deck and explain why it's a KEEP. Ensure the hand includes at least 2-3 Lands and realistic mana sources!)

Constraints:
- Define jargon (explain what "Storm", "Buyback", and "Cost Reduction" mean).
- Keep the reading level accessible.
"""

def generate_primer(l2b_analysis, l3_assessment, l1_data, commander_name):
    # 1. Find all cards mentioned in the Layer 2b analysis
    mentioned_cards = set()
    mentioned_cards.add(commander_name)
    
    for cat in l2b_analysis.get("functional_categories", []):
        mentioned_cards.update(cat.get("key_cards", []))
    for chain in l2b_analysis.get("velocity_chains", []):
        mentioned_cards.update(chain.get("key_cards", []))
        mentioned_cards.update(chain.get("refueling_cards", []))
    for win in l2b_analysis.get("win_conditions", []):
        mentioned_cards.update(win.get("key_cards", []))

    # 2. Extract the exact oracle text for ONLY those cards
    key_cards_text = ""
    for card in l1_data:
        if card["name"] in mentioned_cards:
            text = card.get("oracle_text", "").replace("\n", " ")
            key_cards_text += f"- **{card['name']}**: {text}\n"

    l3_text = "Not provided."
    if l3_assessment:
        l3_text = f"""
        Power Bracket: {l3_assessment.get('power_bracket')}
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
    
    Write the primer.
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

# You can leave the __main__ block as is for testing

if __name__ == "__main__":
    with open("cache/vadrik_time_l2b.json", "r") as f:
        l2b_data = json.load(f)["analysis"]
        
    with open("cache/vadrik_time_l1.json", "r") as f:
        l1_data = json.load(f)["records"]
        
    # Try to load L3
    try:
        with open("cache/vadrik_time_l3.json", "r") as f:
            l3_data = json.load(f)["assessment"]
    except FileNotFoundError:
        print("Layer 3 cache not found. Running without power assessment.")
        l3_data = None
        
    primer_text = generate_primer(
        l2b_data, 
        l3_data,
        l1_data, 
        "Vadrik, Astral Archmage"
    )
    
    print("\n--- PRIMER OUTPUT ---\n")
    print(primer_text)