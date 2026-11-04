#import test3deckparse
import ollama
import card as Cards
import json
import test

def extract_card_facts(card):
    """Extract deterministic facts directly from Scryfall data."""
    text = card.getText().lower()
    abilities = text.split("\n")
    synergy = []
    for ability in abilities:
        if "instead" in ability:
            synergy.append("replacement effect")

        if "whenever" in ability and "instead" not in ability:
            synergy.append("triggered ability")

    return {
        "name": card.getName(),
        "mana_cost": card.getCost(),
        "type": card.getType(),
        "oracle_text": card.getText(),
        "synergy": synergy
    }

def validate_card_role(card_facts):
    system_prompt = """
    You are a strict Magic: The Gathering rules classification engine.
    Magic: the Gathering is a game of resource management, with the main goal being to win by either performing a combat win (depleting the enemy's life total starting from 40 to 0 utilising the combat phase), or a non-combat win (playing cards that either state "You win the game", or invoke a "State-Based-Action" game loss trigger (e.g. a player loses the game when they attempt to interact with their library and have no cards in their library).)
    Analyze the provided card strictly by its Oracle Text and respond ONLY with valid JSON matching the exact schema requested.

    Allowed Primary Roles & Strict Definitions:
    - Card Advantage: Must explicitly involve drawing cards, reanimating, or tutoring/searching libraries. (Cost reduction is NOT card advantage).
    - Interaction: Counterspells, removal, board wipes, stax effects, or direct disruption of opponents.
    - Ramp: Mana acceleration, extra lands, treasures, or cost reduction of spells (making spells cost less).
    - Win Condition: Direct damage/drain to life totals, explicit combo pieces, or heavy combat finishers.
    - Misc. Value: Value enginees, Trigger ability doublers, recursion spells (that move creatures from the graveyard to the battlefield), lifegain effects, 

    Rules:
    1. Do not invent non-existent mechanics.
    2. Keep justification to exactly ONE sentence based ONLY on the Oracle text.
    3. ABSOLUTE RULE: If a keyword does not appear in the oracle text, you are STRICTLY FORBIDDEN from stating that the card performs said keyword (e.g. "Draw" does not appear in an oracle text --> you are forbidden from saying that the card draws cards)

    Classification Rules:
    - Card Advantage: Cards including the keyword "Draw", cards that provide extra cards to the player from undesired zones (e.g. moving cards from the graveyard, library, exile, or the command zone to the hand)
    - Ramp: Cards that include the keyword "Add", cards that either individually generate one of either colourless ({{1}}+), or coloured mana ({{W}}/{{U}}/{{B}}/{{R}}/{{G}}, etc) or generate objects that can create mana (e.g. a creature that with a tap cost that adds {{G}}, or a spell that creates Treasure Tokens/allows the user to play more lands), cards that decrease the cost of other cards
    - Interaction: Cards that include the keyword "Opponent", cards that allow the player to target/interact with an opponent, e.g. removal spells (Destroy target creature), counterspells (Counter target spell), etc
    - Win Conditions: Cards that can convert any boardstate into a win. Combat win conditions include cards that add to creature power and or toughness, increase the number of combat phases, etc. Non-combat win conditions include oracle texts with "You win the game", spells that actively decrease the health of the opponent, or synergies between cards that loop infinitely.
    - Misc. Value Engine: Cards that do not fit the above categories, and can consistently provide some sort of advantage
    """
    
    user_prompt = f"""
    Card Data:
    - Name: {card_facts['name']}
    - Type: {card_facts['type']}
    - Cost: {card_facts['mana_cost']}
    - Text: {card_facts['oracle_text']}
    - Synergies: {card_facts['synergy']}

    Return JSON in this format:
    {{
      "primary_role": "One of the Allowed Primary Roles",
      "summary": "Short 1-sentence mechanical summary based strictly on Oracle text and analyse potential synergies if any (explicitly within synergy_hooks).",
      "justification": "Justification of primary role based completely on oracle text.",
      "synergy_hooks": ["List any key triggers, keywords, or loop enablers present, e.g., 'Copy', 'Whenever you cast', 'Buyback', or leave empty if none."] 
    }}
    """
    
    response = ollama.chat(
        model="llama3.2",
        format="json",  # Enforces JSON output from Ollama
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    # Parse string into Python dictionary
    return json.loads(response['message']['content'])

"""testjson = {
    'name': 'Brainstorm', 
    'oracle_text': 'Draw three cards, then put two cards from your hand on top of your library in any order.', 
    'type_line': 'Instant', 
    'mana_cost': "U"
}"""

"""testjson = {
    'name': 'Vadrik, Astral Archmage', 
    'oracle_text': If it's neither day nor night, it becomes day as Vadrik enters.
Instant and sorcery spells you cast cost {{X}} less to cast, where X is Vadrik's power.
Whenever day becomes night or night becomes day, put a +1/+1 counter on Vadrik., 
    'type_line': 'Legendary Creature — Human Wizard', 
    'mana_cost': "{{1}}{{U}}{{R}}",
    'power': '1',
    'toughness': '2'
}"""


#temp card
tempcard = test.search("miirym") #Cards.createCard(testjson, 1, "Ramp")
facts = extract_card_facts(tempcard)
result = validate_card_role(facts)
print(tempcard.getName())
print(json.dumps(result, indent=2))


#for card in deck:
#    print(validate_card_role(extract_card_facts(card)) + "\n")