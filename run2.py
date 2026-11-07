import json
import os
import test2_layer2a
import test2_layer2b
import test2_llm
import test3deckparse

CACHE_FILE1 = "card_cache.json"
CACHE_FILE2 = "layer1_cache.json"
CACHE_FILE3 = "layer2a_cache.json"
CACHE_FILE4 = "layer2b_cache.json"

# Check if cache exists; if not, parse live deck once and save it
if os.path.exists(CACHE_FILE1):
  print(f"Loading cached Layer 1 data from {CACHE_FILE1}...")
  with open(CACHE_FILE1, "r", encoding="utf-8") as f:
    layer1cache = json.load(f)
else:
  print("No cache found. Querying web/Scryfall for Layer 1...")
  url = "https://archidekt.com/decks/6429634/vadrik_time"
  deck = test3deckparse.parseArchiURL(url)

  layer1cache = []
  for card in deck:
    layer1cache.append(test2_llm.extract_card_facts(card))
  with open(CACHE_FILE1, "w", encoding="utf-8") as f:
    json.dump(layer1cache, f, indent=2)
print("Loaded card data.")


if os.path.exists(CACHE_FILE2):
  print(f"Loading cached Layer 1 data from {CACHE_FILE2}...")
  with open(CACHE_FILE2, "r", encoding="utf-8") as f:
    layer1 = json.load(f)
else: 
    layer1 = []
    for fact in layer1cache:
        analysis = test2_llm.validate_card_role(fact)
        layer1.append(analysis)

    with open(CACHE_FILE2, "w", encoding="utf-8") as f:
        json.dump(layer1, f, indent=2)

print("Layer 1 data ready.")
print("--------------------------------------------------------------------------------")

# Proceed instantly to Layer 2A and 2B
if os.path.exists(CACHE_FILE3):
   print(f"Loading cached Layer 2a data from {CACHE_FILE3}")
   with open(CACHE_FILE3, "r", encoding="utf-8") as f:
      layer2a_graph = json.load(f)
else:
    layer2a_graph = test2_layer2a.build_layer2a_graph(layer1)
    with open(CACHE_FILE3, "w", encoding="utf-8") as f:
        json.dump(layer2a_graph, f, indent=2)

if os.path.exists(CACHE_FILE4):
   print(f"Loading cached Layer 2b data from {CACHE_FILE4}")
   with open(CACHE_FILE4, "r", encoding="utf-8") as f:
      layer2b_output = json.load(f)
else:
    layer2b_output = test2_layer2b.generate_layer2b_engines(
        layer2a_graph, "Vadrik, Astral Archmage"
    )
    with open(CACHE_FILE4, "w", encoding="utf-8") as f:
       json.dump(layer2b_output, f, indent=2)

print(json.dumps(layer2b_output, indent=2))