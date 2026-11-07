#import test3deckparse
import ollama
import card as Cards
import json

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
        "synergy": list(set(synergy))
    }

#Magic: the Gathering is a game of resource management, with the main goal being to win by either performing a combat win (depleting the enemy's life total starting from 40 to 0 utilising the combat phase), or a non-combat win (playing cards that either state "You win the game", or invoke a "State-Based-Action" game loss trigger (e.g. a player loses the game when they attempt to interact with their library and have no cards in their library).)
#Each card can be separated into either lands (which can only be played from one's hand once per turn unless explicitly stated otherwise), or spells, which each have a "mana cost", which is a resource cost that lands can tap for (once tapped, a land can no longer be tapped until it is untapped, either at the start of next turn or unless otherwise explicitly stated) and must be paid for in order for the spell to take effect (i.e. resolve).
#MTG works with a stack based system, i.e. when players cast a spell, activate an ability, or switch phases (e.g. from main phase to combat phase, passing turns) it goes on a stack datastructure, and abilities are able to be triggered by the spell or other players are able to react and respond to it.
#Terminology definitions: Reanimating allow players to move creatures or permanents from their graveyard to the battlefield, typically at a cost. Tutoring corresponds with searching a player's library for a constant amount of cards (typically 1). Counterspells allow players to react to and deny a spellcast. Removal corresponds to spells that remove permanents from the battlefield. Stax corresponsd to permanents (typically) that increase the resources necessary to take ingame actions (e.g. casting a spell costs {1} colorless extra.)
    
def validate_card_role(card_facts):
    system_prompt = """
    You are a strict Magic: The Gathering rules classification engine.
    Analyze the provided card strictly by its Oracle Text and respond ONLY with valid JSON matching the exact schema requested.

    Allowed Primary Roles & Strict Definitions:
    - Card Advantage: Must explicitly involve drawing cards, reanimating, or tutoring/searching libraries. (Cost reduction is NOT card advantage).
    - Disruption: Counterspells, removal, board wipes, stax effects, or direct disruption of opponents.
    - Ramp: Mana acceleration, extra lands, treasures, or cost reduction of spells (making spells cost less).
    - Win Condition: Anything that ends the game. Direct damage/disruption/drain to life totals, explicit combo pieces, or heavy combat finishers.
    - Value Engine: Value engines, Trigger ability doublers, recursion spells (that move creatures from the graveyard to the battlefield), lifegain effects.

    Rules:
    1. Do not invent non-existent mechanics.
    2. Keep justification to exactly ONE sentence based ONLY on the Oracle text.
    3. ABSOLUTE RULE: If a keyword does not appear in the oracle text, you are STRICTLY FORBIDDEN from stating that the card performs said keyword (e.g. "Draw" does not appear in an oracle text --> you are forbidden from saying that the card draws cards)
    4. Triggered abilities that trigger on an archetype may not belong to the same archetype. For the role, look explicitly at the result of the ability instead of the trigger, for the synergy_hooks, add the role of the trigger.

    MANDATORY SEMANTIC CORRELATION RULES FOR SYNERGY HOOKS:
    When extracting synergy_hooks, do not just copy-paste keywords. Map out the semantic and mechanical consequences implied by the text:
    1. Zone Changes & Triggers: If a mechanic forces a permanent to be sacrificed, exiled, discarded, milled, or put into a graveyard (e.g., Blitz, Escape, Flashback, Explore, Destroy), explicitly tag the implied zone transitions (e.g., "Zone: Battlefield -> Graveyard" due to creature death). Similarly, if a mechanic forces a card to go into hand, this is also treated as a zone change (e.g. "Zone: Library -> Hand" from drawing a card, or "Zone: Graveyard -> Hand" from recursion effects, "Zone: Battlefield -> Hand" from bounce effects, or "Zone: Stack -> Hand" from Reprieve-like or buyback effects)
    2. Cost vs. Payoff: If an ability requires a cost (like paying life, sacrificing, discarding, or tapping), tag the resource type consumed. If it provides a benefit (like drawing cards, adding mana, or reducing costs), tag the resource type produced.
    3. Action-Reaction: If an effect triggers on an action (e.g., "Whenever you cast", "Whenever a creature dies"), tag both the trigger condition and the resulting output so it can match complementary cards in a graph.

    Classification Rules:
    - Card Advantage: Cards including the keyword "Draw", cards that provide extra cards to the player from undesired zones (e.g. moving cards from the graveyard, library, exile, or the command zone to the hand)
    - Ramp: Cards that include the keyword "Add", cards that either individually generate one of either colourless ({{1}}+), or coloured mana ({{W}}/{{U}}/{{B}}/{{R}}/{{G}}, etc) or generate objects that can create mana (e.g. a creature that with a tap cost that adds {{G}}, or a spell that creates Treasure Tokens/allows the user to play more lands), cards that decrease the cost of other cards
    - Disruption: Cards that target/disrupt with specifically a permanent or spell an opponent controls, e.g. removal spells (Destroy target creature), counterspells (Counter target spell), etc
    - Win Conditions: Cards that can convert any boardstate into a win. Combat win conditions include cards that add to creature power and or toughness, increase the number of combat phases, etc. Non-combat win conditions include oracle texts with "You win the game", spells that actively decrease the health of the opponent by a large amount (e.g. >= 10), or synergies between cards that loop infinitely.
    - Value Engine: Cards that do not fit the above categories, and can consistently (i.e. repeatedly) provide some sort of resource advantage, e.g. consistently draws cards, consistently generates mana, consistently provides card information (e.g. playing with a top card of library revealed, scry (allows the player to look at the top card of their library once, then allows them to choose to leave it on top (as known information), or move it to the bottom of their library)), consistent small (i.e. < 5) amounts of damage from a triggered ability.
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
      "synergy_hooks": ["Extract structural properties or impact of the spell, such as: 'Cost Reducer (Static/Variable)', 'Alternative Cost: Flashback (for example, other alternative costs apply, like overload)', 'Additional Cost: Buyback (for example, other additional costs also apply, such as kicker, multikicker, etc)', 'Mana Generator (e.g. Mana rock, Ritual)', 'Spell Copier', or 'Variable X Scaling'. Do not hardcode card names—only describe what the text structurally enables. List all key triggers, keywords present, e.g., 'Copy', 'Whenever you cast', 'Buyback', "Menace", "graveyard", mention of a specific card type, Any explicit effect of the card, or leave empty if none."],
      "secondary_role": ["List any remaining potential roles that this card may fulfill outside of the primary role, can be none if the card purely fulfills one role. Do not assume anything outside of the card, solely look at this individual card's oracle text, do not extrapolate any information or any potentiality."],
      "justification_secondary": ["List all justifications for secondary roles if any, otherwise leave blank. Do not assume anything outside of the card, solely look at this individual card's oracle text."]
    }}
    """
    
    response = ollama.chat(
        model="qwen2.5:32b",
        format="json",  # Enforces JSON output from Ollama
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    parsed = json.loads(response["message"]["content"])

    # FORCE Python to own these fields so they can never cause KeyErrors
    parsed["name"] = card_facts["name"]
    parsed["type"] = card_facts["type"]
    parsed["cost"] = card_facts["mana_cost"]
    parsed["text"] = card_facts["oracle_text"]
    return parsed

"""
testjson = test.search("Henzie")
#i = Cards.createCard(testjson, 1, "Card Draw")
facts = extract_card_facts(testjson)
result = validate_card_role(facts)
print(testjson.getName())
print(json.dumps(result, indent=2))

testjson = {
    'name': 'Vadrik, Astral Archmage', 
    'oracle_text': "If it's neither day nor night, it becomes day as Vadrik enters.
Instant and sorcery spells you cast cost {{X}} less to cast, where X is Vadrik's power.
Whenever day becomes night or night becomes day, put a +1/+1 counter on Vadrik.", 
    'type_line': 'Legendary Creature — Human Wizard', 
    'mana_cost': "{{1}}{{U}}{{R}}",
    'power': '1',
    'toughness': '2'
}
testjson = {
    'name': 'Brainstorm', 
    'oracle_text': 'Draw three cards, then put two cards from your hand on top of your library in any order.', 
    'type_line': 'Instant', 
    'mana_cost': "U"
}
"""
"""
#temp card
tempcard = [test.search("Harnfel, Horn of Bounty")]
#Cards.createCard(testjson, 1, "Ramp")

for i in tempcard:
    facts = extract_card_facts(i)
    result = validate_card_role(facts)
    print(i.getName())
    print(json.dumps(result, indent=2))
"""

#for card in deck:
#    print(validate_card_role(extract_card_facts(card)) + "\n")