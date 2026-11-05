import json
import ollama
import card as Cards
import test


def extract_card_facts(card):
  """Extract deterministic mechanical hooks using basic string matching

  without hardcoding card-specific archetypes.
  """
  text = card.getText().lower()
  hooks = []

  if "whenever you cast" in text or "when you cast" in text:
    hooks.append("cast_trigger")
    if "copy" in text:
        hooks.append("copy_engine")
  if "scry" in text:
    hooks.append("scry")
  if "create" in text and "token" in text:
    hooks.append("token_generation")
  if "trigger" in text and "additional time" in text:
    hooks.append("trigger_doubler")
  if "deals" in text and "damage" in text:
    hooks.append("direct_damage")

  return {
      "name": card.getName(),
      "mana_cost": card.getCost(),
      "type": card.getType(),
      "oracle_text": card.getText(),
      "synergy_hooks": hooks,
  }


def validate_card_role(card_facts):
  system_prompt = """
    You are a strict Magic: The Gathering card classifier.
    Analyze the card's Oracle Text and respond ONLY with valid JSON.

    Primary Roles (Pick EXACTLY One):
    - Card Advantage: Draws cards, searches/tutors library, or moves cards from graveyard/exile to hand.
    - Disruption: Counterspells, targeted removal of opponent permanents, board wipes, or stax resource taxes.
    - Ramp: Adds mana directly, plays extra lands, creates Treasure tokens, or reduces spell mana costs.
    - Win Condition: Direct damage/drain to life totals, infinite combo pieces, or massive combat scaling.
    - Value Engine: Resource engines, token creation, spell-copy multipliers, trigger doublers, or static utility.

    Absolute Preconditions & Guardrails:
    1. Base classification strictly on printed Oracle text without extrapolation. 
    2. Keep justification to ONE sentence.
    3. Use EXACTLY what is on the Card Data of the specific card, and NOTHING more.
    4. RAMP RESTRICTION: A card can ONLY be classified as "Ramp" if its Oracle text explicitly contains the words "add" (followed by some mana value, e.g. an integer, U, W, B, R, G, or any permutation of the above etc), "land", "search your library for a land", or "cost less". If a card does not mention mana or lands, Ramp is STRICTLY FORBIDDEN.
    5. Dealing damage to an opponent or creating tokens is NEVER Disruption. Disruption requires removing or countering opponent assets (e.g. permanents or spells on the stack).
    """

  user_prompt = f"""
    Card Data:
    - Name: {card_facts['name']}
    - Type: {card_facts['type']}
    - Cost: {card_facts['mana_cost']}
    - Text: {card_facts['oracle_text']}
    - Detected Hooks: {card_facts['synergy_hooks']}

    Return JSON in this exact structure:
    {{
      "primary_role": "One of the Primary Roles",
      "summary": "Short 1-sentence summary based strictly on Oracle text.",
      "justification": "One sentence justifying the role based on Oracle text.",
      "secondary_role": [],
      "justification_secondary": []
    }}
    """

  response = ollama.chat(
      #model="llama3.1:8b",
      model="qwen2.5:14b",
      format="json",
      messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
      ],
  )

  parsed = json.loads(response["message"]["content"])
  parsed["synergy_hooks"] = card_facts["synergy_hooks"]
  return parsed


# Test execution without hardcoded rules
tempcard = [
    test.search("veyran, voice of duality"),
    test.search("zaffai, thunder conductor"),
]

for card in tempcard:
  facts = extract_card_facts(card)
  result = validate_card_role(facts)
  print(card.getName())
  print(json.dumps(result, indent=2))