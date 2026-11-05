"""Conservative mechanical checks for model-extracted reported fields.

Skip fields when a source value, timezone, or currency cannot be established.
This checks textual consistency, not the actual truth of a source.
"""

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def source_value_check(claim):
    value = str(claim.get("value", "")).strip()
    if not value:
        return "not_comparable"
    compact = lambda x: re.sub(r"\s+", "", x.casefold())
    return (
        "value_in_quote"
        if compact(value) in compact(claim.get("quote", ""))
        else "value_not_found_in_quote"
    )


def normalized(claim):
    field = claim["field"]
    value = claim["value"].strip()
    if field == "delivery_date":
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if d.tzinfo is None:
                return None
            return d.astimezone(timezone.utc).isoformat()
        except ValueError:
            return None
    if field == "amount":
        m = re.fullmatch(r"([A-Z]{3})\s+([0-9]+(?:\.[0-9]+)?)", value)
        if not m:
            return None
        try:
            return m[1] + " " + str(Decimal(m[2]).normalize())
        except InvalidOperation:
            return None
    if field in ("destination_postcode", "tracking_number"):
        return re.sub(r"\s+", "", value).casefold()
    if field in ("product_model", "refund_status"):
        return re.sub(r"\s+", " ", value).casefold()
    return None


def compare(claims):
    groups = {}
    found = []
    for claim in claims:
        if (
            claim.get("semantic_support") != "entailed"
            or source_value_check(claim) != "value_in_quote"
        ):
            continue
        key = (claim.get("subject", "").strip().casefold(), claim.get("field", ""))
        value = normalized(claim)
        if not key[0] or value is None:
            continue
        groups.setdefault(key, []).append((claim, value))
    for (subject, field), rows in groups.items():
        values = {v for _, v in rows}
        if len(values) < 2:
            continue
        found.append(
            {
                "id": f"X{len(found) + 1}",
                "subject": subject,
                "field": field,
                "claim_ids": [r["id"] for r, _ in rows],
                "description": f"Reported {field.replace('_', ' ')} values differ: "
                + " / ".join(sorted(values)),
                "verification": "Deterministic comparison of values present in quoted sources. Dates require explicit timezones and amounts require currencies. Entity/field alignment is model-extracted and requires human scope review.",
            }
        )
    return found
