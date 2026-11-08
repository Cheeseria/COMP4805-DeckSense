# card.py
"""
Canonical Card class + factory. This is the normalization boundary between
ingestion and every downstream layer. Extend here, not in search.py.
"""


class Card:
    def __init__(self, name, cost, card_type, oracle_text, statline,
                 role, amount, *, keywords=None, cmc=None,
                 color_identity=None, oracle_id=None, is_commander=False,
                 user_categories=None):
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.oracle_text = oracle_text
        self.statline = statline
        self.role = role              # user tag(s) string (legacy); see user_categories
        self.amount = amount
        self.keywords = list(keywords or [])
        self.cmc = cmc                # mana value (float or None)
        self.color_identity = list(color_identity or [])
        self.oracle_id = oracle_id
        self.is_commander = bool(is_commander)
        self.user_categories = set(user_categories or [])
        # Keep role as first tag for backwards-compat with existing code paths.
        if not self.user_categories and role:
            self.user_categories = {role}

    # --- getters (legacy) ---
    def getName(self):    return self.name
    def getCost(self):    return self.cost
    def getType(self):    return self.card_type
    def getText(self):    return self.oracle_text
    def getStat(self):    return self.statline
    def getRole(self):    return self.role
    def getAmount(self):  return self.amount

    def __repr__(self):
        return f"<Card {self.name} cmc={self.cmc} commander={self.is_commander}>"


def createCard(json, num, category, *, is_commander=False, user_categories=None):
    """Build a Card from a Scryfall card JSON object (single face or whole card).

    Guards all optional fields; DFC faces may omit mana_cost, power, etc.
    """
    name = json.get("name", "")
    cost = json.get("mana_cost", "") or ""
    oracle_text = json.get("oracle_text", "") or ""
    card_type = json.get("type_line", "") or ""

    if "Creature" in card_type and "power" in json and "toughness" in json:
        statline = f"{json['power']} / {json['toughness']}"
    elif "Planeswalker" in card_type:
        statline = json.get("loyalty", "") or ""
    elif "Battle" in card_type:
        statline = json.get("defense", "") or ""
    else:
        statline = ""

    cats = set(user_categories or [])
    if category:
        cats.add(category)

    return Card(
        name=name,
        cost=cost,
        card_type=card_type,
        oracle_text=oracle_text,
        statline=statline,
        role=category or "",
        amount=num,
        keywords=json.get("keywords", []) or [],
        cmc=json.get("cmc"),
        color_identity=json.get("color_identity", []) or [],
        oracle_id=json.get("oracle_id"),
        is_commander=is_commander,
        user_categories=cats,
    )