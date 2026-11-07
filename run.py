import test3deckparse
import test2_llm
import test1_layer2
import json

url = 'https://archidekt.com/decks/6429634/vadrik_time'
deck = test3deckparse.parseArchiURL(url)

layer1 = []

for card in deck:
    layer1.append(test2_llm.validate_card_role(test2_llm.extract_card_facts(card)))

print("Layer 1 done")

layer2_1 = test1_layer2.build_layer2_payload(layer1)
layer2_graph = test1_layer2.generate_synergy_graph(layer2_1, "Vadrik, Astral Archmage")
layer2_coherence = test1_layer2.calculate_deck_coherence(layer2_1, layer2_graph)

print(layer2_graph)
print(" ----------------------------------------- ")
print(layer2_coherence)