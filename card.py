class Card: 
#self - refers to instance; name - refers to the name of the card; cost - includes WUBRG symbols, shows cost of a card; card_type - 
    def __init__(self, name, cost, card_type, oracle_text, statline, role, amount):
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.oracle_text = oracle_text
        self.statline = statline
        self.amount = amount
        self.role = role
    
    def getName(self):
        return self.name

    def getCost(self):
        return self.cost
    
    def getType(self):
        return self.card_type

    def getText(self):
        return self.oracle_text
    
    def getStat(self):
        return self.statline
    
    def getRole(self):
        return self.role

    def getAmount(self):
        return self.amount

def createCard(json, num, category):
    name = json["name"]
    cost = json["mana_cost"]
    oracle_text = json["oracle_text"]
    card_type = json["type_line"]
    if "Creature" in card_type:
        statline = json["power"] + " / " + json["toughness"]
    elif "Planeswalker" in card_type:
        statline = json["loyalty"]
    elif "Battle" in card_type:
        statline = json["defense"]
    else:
        statline = ""

    return Card(name=name, cost=cost, card_type=card_type, oracle_text=oracle_text, statline=statline, role=category, amount=num)