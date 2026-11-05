from test3deckparse import *
import ollama

system_context = """
You are an expert Magic: The Gathering EDH deck analyst. 
CRITICAL RULE: You must ONLY use the exact Oracle text provided for each card. Do not guess what cards do. If a card does not draw cards, do not claim it draws cards. 

Example of accurate analysis:
- Card: Brain Freeze -> A storm spell used in storm/combo decks to mill opponents out by leveraging high storm counts, not a draw spell.
- Card: Mana Drain -> A counterspell that generates colorless mana equal to the countered spell's mana value in your next main phase.
"""

card_data_str = "\n".join(
    f"- {card.getName()} | Mana Cost: {card.getCost()} | Role: {card.getRole()} | Text: {card.getText()}" 
    for card in deck
)

user_prompt = f"""
Generate a structured Deck Primer based on the following cards:

{card_data_str}

Please include the following sections:
1. **Deck Overview & Strategy**: High-level playstyle and goals.
2. **Key Win Conditions**: Infinite combos, synergy engines, or combat setups.
3. **Core Synergies & Role Breakdown**: How cards fulfilling specific roles interact.
4. **Interactive & Smart Plays**: Key timing, counterplays, and tactical decisions.
"""

response = ollama.chat(
    model="llama3.2",
    messages=[
        {"role": "system", "content": system_context},
        {"role": "user", "content": user_prompt}
    ]
)

print(response['message']['content'])