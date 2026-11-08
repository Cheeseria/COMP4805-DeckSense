# layer2c.py
import json
import ollama

# We keep the LLM prompt to catch semantic errors (e.g., "this card doesn't do what you think it does")
FACT_CHECK_SYSTEM_PROMPT = """
You are a strict Magic: The Gathering Rules Judge.
You are reviewing proposed combos. 
1. Read the proposed loop.
2. If the loop relies on a mechanic that is NOT on the cards (e.g., claiming a card reduces costs when it doesn't), REJECT the loop.
3. Output JSON. If valid, say true. If invalid, say false.
"""

def _python_mana_check(loop_cards, cited_data, required_assumptions=None):
    required_assumptions = required_assumptions or []
    total_cost = 0
    has_mana_generator = False

    for card in loop_cards:
        data = cited_data.get(card, {})
        cmc = data.get("mana_value", 0)
        text = data.get("oracle_text", "").lower()
        total_cost += cmc
        if any(k in text for k in ("add {", "adds {", "treasure", "add one mana")):
            has_mana_generator = True

    # If no card in the loop generates mana, check if a mana source is named in assumptions
    if total_cost > 0 and not has_mana_generator:
        assumption_text = " ".join(required_assumptions).lower()
        mana_keywords = ("mana", "seething song", "dark ritual", "sol ring", "lotus petal",
                         "mana geyser", "cabal ritual", "inner fire", "jeska's will",
                         "treasure", "cost reduc", "vadrik", "goblin electromancer")
        if not any(k in assumption_text for k in mana_keywords):
            return False, f"Total mana cost is {total_cost}, but no mana source or cost reducer is named in the loop or its assumptions."

    return True, "Passed basic mana check."


def fact_check_loops(analysis_output, graph, model="qwen2.5:32b"):
    if not analysis_output.get("validated_cycles") and not analysis_output.get("win_conditions_and_loops"):
        return analysis_output

    proposed_loops = analysis_output.get("validated_cycles", []) + analysis_output.get("win_conditions_and_loops", [])
    cited_data = analysis_output.get("_cited_card_data", {})
    
    final_validated = []
    final_rejected = analysis_output.get("rejected_loops", []) # Keep previous rejections

    for loop in proposed_loops:
        cards = loop.get("cards", loop.get("key_cards", []))
        
        # 1. PYTHON CHECK: Fast, hard logic
        py_valid, py_reason = _python_mana_check(
            cards, cited_data,
            required_assumptions=loop.get("required_assumptions", [])
        )
        
        if not py_valid:
            final_rejected.append({
                "original_cycle": cards,
                "is_valid": False,
                "hallucination_reason": f"Python Arithmetic Check Failed: {py_reason}"
            })
            continue # Skip the LLM check, we already know it's fake

        # 2. LLM CHECK: Semantic logic (if Python passes)
        user_prompt = f"""
        PROPOSED LOOP: {json.dumps(cards)}
        MATH: {loop.get('mechanical_validation')}
        
        ORACLE TEXT:
        {json.dumps({c: cited_data.get(c, {}) for c in cards}, indent=2)}
        
        Does this loop actually work? Look closely at the Oracle text. Do the cards do what the math claims?
        """
        
        try:
            resp = ollama.chat(model=model, format="json", options={"temperature": 0, "num_ctx": 4096},
                messages=[{"role": "system", "content": FACT_CHECK_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}])
            checked = json.loads(resp["message"]["content"])
            
            if checked.get("is_valid"):
                final_validated.append(loop)
            else:
                final_rejected.append({
                    "original_cycle": cards,
                    "is_valid": False,
                    "hallucination_reason": checked.get("hallucination_reason", "LLM rejected semantic logic.")
                })
        except Exception as e:
            # If LLM fails, default to rejecting
            final_rejected.append({"original_cycle": cards, "is_valid": False, "hallucination_reason": str(e)})

    analysis_output["validated_cycles"] = final_validated
    analysis_output["win_conditions_and_loops"] = final_validated
    analysis_output["rejected_loops"] = final_rejected
    
    return analysis_output