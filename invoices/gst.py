import os
import re


def normalize_state(state):
    state = re.sub(r"[^a-z]", "", (state or "").lower())

    # Handle common spellings and variations.
    aliases = {
        "tamilnadu": "tamilnadu",
        "tamilnad": "tamilnadu",
        "tn": "tamilnadu",
    }

    return aliases.get(state, state)


def determine_gst_type(seller_state, customer_state):
    seller = normalize_state(seller_state)
    customer = normalize_state(customer_state)

    if not seller or not customer:
        raise ValueError("Seller state and customer state are required.")

    return (
        "intra_state"
        if seller == customer
        else "inter_state"
    )


def get_seller_state():
    return os.getenv("SELLER_STATE", "Tamil Nadu").strip()