import json
l1 = json.load(open("cache/vadrik_time_l1.json"))["records"]
reit = next(r for r in l1 if r["name"] == "Reiterate")
print("Reiterate hooks in cached L1:", [h.get("kind") for h in reit.get("synergy", [])])