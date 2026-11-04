import requests
import urllib.parse
import card as Cards

def search(inp):
    param = inp#urllib.parse.quote(inp)
    search = 'https://api.scryfall.com/cards/named'

    x = requests.get(search, params={"fuzzy": param}, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0", "Accept": "application/json;q=0.9,*/*;q=0.8"})

    json = x.json()
    #name = json["name"]

    card = Cards.createCard(json, 1, "Test")
    return card

'''
    print("Name: " + card.getName())
    print("CMC: " + card.getCost())
    print("Text: " + card.getText())
    print("Type: " + card.getType())
    print("Stat Line: " + card.getStat())
'''
