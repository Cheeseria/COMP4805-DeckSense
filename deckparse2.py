import ollama
import card as Cards
import json
import test
import card as Cards
from time import sleep

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

    Analyse card interactions and triggered abilities. If a card resolves an ability that triggers an ability in a different card, they are stated to have a synergy.



    """
    
    user_prompt = f"""
    Card Data:
    - Name: {card_facts['name']}
    - Type: {card_facts['type']}
    - Cost: {card_facts['mana_cost']}
    - Text: {card_facts['oracle_text']}
    - Synergies: {card_facts['synergy']}
    - Primary Role: {card_facts['role']}
    - Previously LLM Analysed Summary: {card_facts['summary']}
    - OracleText based Justification for Role: {card_facts['justification']}
    - Preanalysed potential synergies: {card_facts['synergy']}

    Return JSON in this format:
    {{
      "primary_synergy": ["Synergy Roles, or in other words, archetypes that this card specifically synergises with, and the commonality of this archetype in the list"],
      "summary": "Short 1-sentence mechanical summary for each synergy based strictly on Oracle text.",
      "justification": "Justification of synergies based completely on oracle text.",
      "synergised_cards": ["(List any cards that align with any of the aforementioend primary synergy roles, [relevant synergy role])"] 
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

"""
import ollama
import card as Cards
import json
import card as Cards
from time import sleep

def group_cards_by_role(validated_deck):
    """Groups pre-validated cards from Layer 1 into functional categories."""
    buckets = {
        "Ramp": [],
        "Card Advantage": [],
        "Interaction": [],
        "Win Condition": [],
        "Utility": []
    }
    for card in validated_deck:
        role = card.get("primary_role", "Utility")
        if role in buckets:
            buckets[role].append({
                "name": card["name"],
                "type": card["type"],
                "oracle_text": card["oracle_text"],
                "synergy_hooks": card.get("synergy_hooks", [])
            })
    return buckets

def generate_synergy_map(role_buckets):
    system_prompt = """
    You are an expert Magic: The Gathering Commander architect. 
    Your task is to analyze the provided deck components grouped by role and map them into functional sub-engines and a cohesive synergy graph.
    
    Identify:
    1. Sub-engines (clusters of 2+ cards that create loops, cost reductions, scaling damage, or infinite combos).
    2. Dead weight candidates (cards with synergy hooks or roles that do not connect to any active engine).
    
    Respond ONLY with valid JSON matching the exact schema requested.
    """
    
    user_prompt = f"""
    Deck Components by Role:
    {json.dumps(role_buckets, indent=2)}

    Return JSON in this exact format:
    {{
      "engines": [
        {{
          "engine_name": "Name of the sub-engine or loop (e.g., Storm & Cost Reduction Loop)",
          "cards": ["Card Name 1", "Card Name 2"],
          "primary_enabler": "The core piece that makes it work",
          "payoff": "The win condition or resource payoff card",
          "relationship_description": "1 sentence explaining how these cards interact mechanically."
        }}
      ],
      "dead_weight_candidates": [
        {{
          "card_name": "Card Name",
          "reason": "Why this card fails to connect to any active engine or core strategy."
        }}
      ]
    }}
    """
    
    response = ollama.chat(
        model="llama3.2",
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    return json.loads(response['message']['content'])

def grade_synergy_map(synergy_data, total_deck_size=100):
    """Programmatically grades the deck based on graph density and connectedness."""
    engines = synergy_data.get("engines", [])
    dead_weight = synergy_data.get("dead_weight_candidates", [])
    
    # Collect unique cards involved in active engines
    engine_cards = set()
    for engine in engines:
        for card in engine.get("cards", []):
            engine_cards.add(card)
            
    connected_count = len(engine_cards)
    dead_weight_count = len(dead_weight)
    
    # Calculate synergy density ratio
    synergy_density = connected_count / total_deck_size
    
    return {
        "active_engines_found": len(engines),
        "connected_cards": connected_count,
        "dead_weight_count": dead_weight_count,
        "synergy_density_score": round(synergy_density * 100, 2)
    }
"""