import requests
import urllib.parse
import pyrchidekt.api


url = 'https://archidekt.com/decks/6429634/vadrik_time'

id = url.split('/')[4]

deckAPI = pyrchidekt.api.getDeckById(id)

class Card: 
#self - refers to instance; name - refers to the name of the card; cost - includes WUBRG symbols, shows cost of a card; card_type - 
    def __init__(self, name, cost, card_type, oracle_text, statline, amount):
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.oracle_text = oracle_text
        self.statline = statline
        self.amount = amount
    
deck = []

for category in deck.categories:
    for card in category.cards:
        new_card = Card(card.card.oracle_card.name, card.card.oracle_card.cost)
        print(f"\t{card.quantity} {card.card.oracle_card.name}")
    print("")

#a = requests.get(search, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0"})

#print(a)