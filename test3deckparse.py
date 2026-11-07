import requests
#import urllib.parse
import warnings
import pyrchidekt.api #maybe can find osme way to access archidekt api myself
import card as Cards
from time import sleep

warnings.filterwarnings('ignore')  # Suppress all warnings

def parseArchiURL(url):
    id = url.split('/')[4]

    deckAPI = pyrchidekt.api.getDeckById(id)

    deck = []
    for category in deckAPI.categories:
        for card in category.cards:
            #rate limit to 2 requests per second
            sleep(0.5)
        
            #print(f"\t{card.quantity} {card.card.oracle_card.name}")

            param = card.card.oracle_card.name#urllib.parse.quote(card.card.oracle_card.name)
            search = 'https://api.scryfall.com/cards/named'

            x = requests.get(search, params={"fuzzy": param}, headers={"User-Agent":"DeckSense/1.0 (Educational Project)"})

            #add some exception handling for multicard results
            #print(x)
            json1 = x.json()
            if "//" in card.card.oracle_card.name: #adventure, prepared spells, etc
                card1 = Cards.createCard(json1["card_faces"][0], card.quantity, category)
                card2 = Cards.createCard(json1["card_faces"][1], card.quantity, category)
                deck.append(card1)
                deck.append(card2)
            else: 
                new_card = Cards.createCard(json1, card.quantity, category)
                deck.append(new_card)
    return deck

#print(" | ".join(" : ".join([i.getName(), i.getText()]) for i in deck))
#for i in deck:
#    print(i.getName())