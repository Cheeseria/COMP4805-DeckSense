import requests
import urllib.parse
import card as Cards

def search(inp):
    param = inp#urllib.parse.quote(inp)
    search = 'https://api.scryfall.com/cards/named'

    x = requests.get(search, params={"fuzzy": param}, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0", "Accept": "application/json;q=0.9,*/*;q=0.8"})

    json = x.json()
    card = Cards.createCard(json, 1, "Test")
    return card

'''
    print("Name: " + card.getName())
    print("CMC: " + card.getCost())
    print("Text: " + card.getText())
    print("Type: " + card.getType())
    print("Stat Line: " + card.getStat())
'''


param = """{
  "identifiers": [
    {
      "id": "683a5707-cddb-494d-9b41-51b4584ded69"
    },
    {
      "name": "Ancient Tomb"
    },
    {
      "set": "mrd",
      "collector_number": "150"
    }
  ]
}"""

json1 = requests.get('https://api.scryfall.com/cards/collection', params=param, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0", "Accept": "application/json;q=0.9,*/*;q=0.8"})
print(json1)
#search("Henzie").getName()