
import json
import os
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from openai import OpenAI

from invoices.models import Invoice, Customer


# --------------------------------------------------
# BUSINESS DEFAULTS
# --------------------------------------------------

def get_seller_defaults():
    return {
        "seller_name": os.getenv("DEFAULT_SELLER_NAME", "Thaagam").strip(),
        "seller_address": os.getenv("DEFAULT_SELLER_ADDRESS", "").strip(),
        "seller_mobile": os.getenv("DEFAULT_SELLER_NUMBER", "").strip(),
        "seller_state": os.getenv("SELLER_STATE", "Tamil Nadu").strip(),
    }


# --------------------------------------------------
# MOBILE NUMBER HELPERS
# --------------------------------------------------

def normalize_mobile(value):
    """Normalize Indian mobile numbers for lookup."""
    digits = re.sub(r"\D", "", str(value or ""))

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    return digits


# --------------------------------------------------
# STATE AND GST HELPERS
# --------------------------------------------------

def normalize_state(state):
    """Normalize common state spelling variations."""
    state = re.sub(r"[^a-z]", "", str(state or "").lower())

    aliases = {
        "tn": "tamilnadu",
        "tamilnadu": "tamilnadu",
        "tamilnad": "tamilnadu",
    }

    return aliases.get(state, state)


def determine_gst_type(seller_state, customer_state):
    """
    Same state: CGST + SGST.
    Different states: IGST.

    This implements the basic state-comparison rule.
    Actual GST treatment can depend on place-of-supply rules.
    """
    seller = normalize_state(seller_state)
    customer = normalize_state(customer_state)

    if not seller or not customer:
        return ""

    if seller == customer:
        return "intra_state"

    return "inter_state"


# --------------------------------------------------
# CUSTOMER LOOKUP
# --------------------------------------------------

def find_customer_by_mobile(user, mobile):
    """
    Search only the current user's customer records.
    Supports numbers stored with spaces, +91, or leading 0.
    """
    mobile = normalize_mobile(mobile)

    if len(mobile) != 10:
        return None

    customers = Customer.objects.filter(owner=user)

    for customer in customers:
        if normalize_mobile(customer.mobile_number) == mobile:
            return customer

    return None


def apply_customer_details(data, user, seller_state):
    """
    Fill customer details from the database when a matching
    mobile number exists. GST is calculated by the server.
    """
    mobile = normalize_mobile(data.get("customer_mobile", ""))

    if len(mobile) != 10:
        data["customer_found"] = False
        data["customer_lookup_message"] = (
            "Enter a valid 10-digit customer mobile number."
            if mobile
            else ""
        )
        data["gst_type"] = ""
        return data

    customer = find_customer_by_mobile(user, mobile)

    if customer:
        # Database details take priority over AI-extracted details.
        data["customer_name"] = customer.name
        data["customer_address"] = customer.address
        data["customer_state"] = customer.state
        data["customer_mobile"] = customer.mobile_number
        data["customer_found"] = True
        data["customer_lookup_message"] = "Existing customer found."
    else:
        data["customer_found"] = False
        data["customer_lookup_message"] = (
            "Customer not found. Provide the customer's name, "
            "full address, and state."
        )

    data["seller_state"] = seller_state
    data["gst_type"] = determine_gst_type(
        seller_state,
        data.get("customer_state", ""),
    )

    return data


# --------------------------------------------------
# INVOICE NUMBER
# --------------------------------------------------

def generate_invoice_number(user):
    """Generate the next invoice number for this user."""
    prefix = os.getenv("INVOICE_NUMBER_PREFIX", "TH").strip().upper()

    invoices = Invoice.objects.filter(
        owner=user
    ).values_list("invoice_number", flat=True)

    highest = 0
    pattern = re.compile(
        rf"^{re.escape(prefix)}-(\d+)$",
        re.IGNORECASE,
    )

    for number in invoices:
        match = pattern.match(number or "")
        if match:
            highest = max(highest, int(match.group(1)))

    return f"{prefix}-{highest + 1:03d}"


# --------------------------------------------------
# INITIAL DRAFT
# --------------------------------------------------

def create_empty_draft(user):
    defaults = get_seller_defaults()

    return {
        "invoice_number": generate_invoice_number(user),
        "seller_name": defaults["seller_name"],
        "seller_address": defaults["seller_address"],
        "seller_mobile": defaults["seller_mobile"],
        "seller_state": defaults["seller_state"],
        "customer_name": "",
        "customer_address": "",
        "customer_mobile": "",
        "customer_state": "",
        "customer_found": False,
        "customer_lookup_message": "",
        "invoice_date": "",
        "due_date": "",
        "gst_type": "",
        "discount": 0,
        "template": "",
        "notes": "",
        "items": [],
    }


# --------------------------------------------------
# ASSISTANT PAGE
# --------------------------------------------------

@login_required
def assistant_page(request):
    return render(request, "ai_agent/assistant.html")


# --------------------------------------------------
# OPENAI SYSTEM PROMPT
# --------------------------------------------------

SYSTEM_PROMPT = """
You are an intelligent invoice assistant.

Return valid JSON only using this structure:

{
  "data": {
    "invoice_number": "",
    "seller_name": "",
    "seller_address": "",
    "seller_mobile": "",
    "customer_name": "",
    "customer_address": "",
    "customer_mobile": "",
    "customer_state": "",
    "invoice_date": "",
    "due_date": "",
    "discount": 0,
    "template": "template_1",
    "notes": "",
    "items": [
      {
        "description": "",
        "quantity": null,
        "unit_price": null,
        "tax_rate": null
      }
    ]
  }
}

Rules:

- If the customer address explicitly contains a recognizable Indian state,
  extract that state into customer_state.
- For example, "204, Kerala" means customer_state is "Kerala".
- If the user describes one product without specifying quantity,
  use quantity 1.
- Example: "Software for 5000" means description "Software",
  quantity 1, and unit_price 5000.
- Do not invent a GST rate.
- Never ask the user for GST type; the server calculates it.
- Preserve existing draft values unless the user explicitly changes them.
- Extract only information provided by the user or already present in the draft.
- Never invent names, addresses, phone numbers, prices, invoice numbers,
  states, or tax rates.
- Never invent customer details from a mobile number.
- The server will look up the customer using the mobile number.
- If a customer is found, the server's saved customer details take priority.
- Extract customer_state only when explicitly provided by the user.
- Do not choose or calculate gst_type. The server determines GST.
- Convert today, yesterday, and tomorrow using the supplied current date.
- If the user says "a table", "a fridge", or "one table", quantity can be 1.
- Do not infer an item's price from its name.
- Do not infer a customer address from their name.
- Preserve seller defaults already present in the draft.
- Do not assume a tax rate.
- Discount is a monetary amount, not a percentage.
- Extract multiple products as separate items.
- Do not decide whether the invoice is complete. The server validates it.
"""


# --------------------------------------------------
# MERGE AI DATA WITH THE EXISTING DRAFT
# --------------------------------------------------

def merge_invoice_data(previous, incoming):
    """Merge AI fields without erasing collected information."""
    result = dict(previous)
    

    simple_fields = {
        "invoice_number",
        "seller_name",
        "seller_address",
        "seller_mobile",
        "customer_name",
        "customer_address",
        "customer_mobile",
        "customer_state",
        "invoice_date",
        "due_date",
        "discount",
        "template",
        "notes",
    }

    for key in simple_fields:
        value = incoming.get(key)

        if value is not None and value != "":
            result[key] = value

    old_items = result.get("items", [])
    new_items = incoming.get("items", [])

    if not isinstance(old_items, list):
        old_items = []

    if isinstance(new_items, list) and new_items:
        merged_items = []

        for index, item in enumerate(new_items):
            if not isinstance(item, dict):
                continue

            old_item = (
                old_items[index]
                if index < len(old_items)
                and isinstance(old_items[index], dict)
                else {}
            )

            merged_item = dict(old_item)

            for key in (
                "description",
                "quantity",
                "unit_price",
                "tax_rate",
            ):
                value = item.get(key)

                if value is not None and value != "":
                    merged_item[key] = value

            merged_items.append(merged_item)

        if merged_items:
            result["items"] = merged_items

    result.setdefault("items", [])
    return result


# --------------------------------------------------
# MISSING FIELDS
# --------------------------------------------------

def find_missing_fields(data, require_customer_address=True):
    missing = []

    required_fields = [
        ("invoice_number", "invoice number"),
        ("seller_name", "seller/business name"),
        ("seller_address", "seller/business address"),
        ("seller_mobile", "seller mobile number"),
        ("customer_name", "customer name"),
        ("customer_mobile", "customer mobile number"),
        ("customer_state", "customer state"),
        ("invoice_date", "invoice date"),
    ]

    if require_customer_address:
        required_fields.append(
            ("customer_address", "customer address")
        )

    for key, label in required_fields:
        if not str(data.get(key) or "").strip():
            missing.append(label)

    mobile = normalize_mobile(data.get("customer_mobile", ""))

    if mobile and len(mobile) != 10:
        missing.append("valid 10-digit customer mobile number")

    # GST is automatic and is not requested from the user.
    if (
        str(data.get("customer_state") or "").strip()
        and not data.get("gst_type")
    ):
        missing.append("valid seller and customer state")

    items = data.get("items", [])

    if not isinstance(items, list) or not items:
        missing.append("at least one product or service")
        return missing

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            missing.append(f"item {index} description")
            continue

        if not str(item.get("description") or "").strip():
            missing.append(f"item {index} description")

        if item.get("quantity") in (None, ""):
            missing.append(f"item {index} quantity")

        if item.get("unit_price") in (None, ""):
            missing.append(f"item {index} price")

    return missing


def build_missing_question(missing):
    if not missing:
        return "Your invoice details are ready for review."

    labels = {
        "invoice number": "invoice number",
        "seller/business name": "your business name",
        "seller/business address": "your business address",
        "seller mobile number": "your business mobile number",
        "customer name": "the customer's full name",
        "customer address": "the customer's full address",
        "customer mobile number": "the customer's mobile number",
        "customer state": "the customer's state",
        "invoice date": "invoice date",
        "valid 10-digit customer mobile number":
            "a valid 10-digit customer mobile number",
        "valid seller and customer state":
            "valid seller and customer state details",
        "at least one product or service":
            "at least one product or service",
    }

    readable = []

    for field in missing:
        if field in labels:
            readable.append(labels[field])
        elif field.endswith(" description"):
            readable.append(field)
        elif field.endswith(" quantity"):
            readable.append(
                field + " (a single item can have quantity 1)"
            )
        elif field.endswith(" price"):
            readable.append(field)

    return (
        "I have collected some of your invoice details. "
        "Please provide the remaining information: "
        + "; ".join(readable)
        + ". You can answer all of these in one message."
    )


# --------------------------------------------------
# AI INVOICE ASSISTANT ENDPOINT
# --------------------------------------------------

@login_required
@require_POST
def invoice_assistant(request):
    try:
        body = json.loads(request.body or "{}")

        # Reset the current AI invoice draft.
        if body.get("action") == "reset":
            request.session["invoice_ai_draft"] = create_empty_draft(
                request.user
            )
            request.session.modified = True

            return JsonResponse({
                "ok": True,
                "data": request.session["invoice_ai_draft"],
                "message": "New invoice draft started.",
            })

        message = str(body.get("message", "")).strip()

        if not message:
            return JsonResponse(
                {"error": "Please enter your invoice details."},
                status=400,
            )

        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL")

        if not api_key or not model:
            return JsonResponse(
                {
                    "error":
                    "Configure OPENAI_API_KEY and OPENAI_MODEL in .env."
                },
                status=500,
            )

        previous_data = request.session.get("invoice_ai_draft")

        if not isinstance(previous_data, dict):
            previous_data = create_empty_draft(request.user)

        defaults = get_seller_defaults()

        # Enforce seller defaults from the server.
        previous_data["seller_name"] = (
            previous_data.get("seller_name")
            or defaults["seller_name"]
        )
        previous_data["seller_address"] = (
            previous_data.get("seller_address")
            or defaults["seller_address"]
        )
        previous_data["seller_mobile"] = (
            previous_data.get("seller_mobile")
            or defaults["seller_mobile"]
        )
        previous_data["seller_state"] = defaults["seller_state"]

        if not previous_data.get("invoice_number"):
            previous_data["invoice_number"] = generate_invoice_number(
                request.user
            )

        today = timezone.localdate()

        context = (
            f"Current date: {today.isoformat()}\n"
            f"Yesterday: {(today - timedelta(days=1)).isoformat()}\n"
            f"Tomorrow: {(today + timedelta(days=1)).isoformat()}\n"
            f"Existing invoice draft:\n"
            f"{json.dumps(previous_data)}\n\n"
            f"New user message:\n{message}"
        )

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )

        result = json.loads(
            response.choices[0].message.content or "{}"
        )

        incoming = result.get("data", {})

        if not isinstance(incoming, dict):
            raise ValueError("Invalid AI response.")

        allowed = {
            "invoice_number",
            "seller_name",
            "seller_address",
            "seller_mobile",
            "customer_name",
            "customer_address",
            "customer_mobile",
            "customer_state",
            "invoice_date",
            "due_date",
            "discount",
            "template",
            "notes",
            "items",
        }

        incoming = {
            key: value
            for key, value in incoming.items()
            if key in allowed
        }

        data = merge_invoice_data(previous_data, incoming)

        # Preserve the template selected by the user.
        selected_template = request.session.get("selected_invoice_template")

        if selected_template in {
            "template_1",
            "template_2",
            "template_3",
            "template_4",
        }:
            data["template"] = selected_template

        
        # Default missing quantity to 1 for a clearly single-item description.
        message_lower = message.lower()

        single_item_context = not any(
            word in message_lower
            for word in (
                "quantities",
                "multiple units",
                "several",
                "two software",
                "three software",
            )
        )

        if single_item_context:
            for item in data.get("items", []):
                if (
                    isinstance(item, dict)
                    and item.get("quantity") in (None, "")
                    and item.get("description")
                    and item.get("unit_price") not in (None, "")
                ):
                    item["quantity"] = 1


        # Enforce trusted seller defaults again.
        data["seller_name"] = (
            data.get("seller_name") or defaults["seller_name"]
        )
        data["seller_address"] = (
            data.get("seller_address") or defaults["seller_address"]
        )
        data["seller_mobile"] = (
            data.get("seller_mobile") or defaults["seller_mobile"]
        )
        data["seller_state"] = defaults["seller_state"]

        if not data.get("invoice_number"):
            data["invoice_number"] = generate_invoice_number(
                request.user
            )

        # Find the customer and calculate GST on the server.
        data = apply_customer_details(
            data=data,
            user=request.user,
            seller_state=defaults["seller_state"],
        )

        missing = find_missing_fields(data)
        ready = not missing

        request.session["invoice_ai_draft"] = data
        request.session.modified = True

        return JsonResponse({
            "reply": build_missing_question(missing),
            "data": data,
            "missing_fields": missing,
            "ready_for_review": ready,
        })

    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {
                "error":
                "The AI returned an invalid response. Please try again."
            },
            status=502,
        )

    except Exception as exc:
        print(
            f"AI invoice error: {type(exc).__name__}: {exc}"
        )
        return JsonResponse(
            {
                "error":
                "AI request failed. Check the Django terminal."
            },
            status=502,
        )
