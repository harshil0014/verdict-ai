import copy
import pytest
from evaluation.custody_pilot import acquisition


def request():
    return {"requests": [{"title": "Carrier destination record", "question": "What postcode was delivered to?", "priority": "first", "source_custodian": "carrier", "recipient": "seller", "delivery_route": "via_party", "availability": "possibly_available", "distinguishes": ["H1", "H2"]}], "hypotheses": [{"id": "H1"}, {"id": "H2"}]}


LABEL = {"request_pattern": "postcode", "witness_party": "carrier", "followup": "Fictional carrier record"}


def test_forwarding_route_preserves_original_custodian():
    assert acquisition(request(), LABEL)["acquired"]
    direct = request()
    direct["requests"][0].update(recipient="carrier", delivery_route="direct")
    assert acquisition(direct, LABEL)["acquired"]


@pytest.mark.parametrize("change", [{"source_custodian": "seller"}, {"delivery_route": "direct"}, {"delivery_route": "unknown"}, {"availability": "unavailable"}, {"distinguishes": ["nonexistent"]}, {"question": "Please supply unrelated details", "title": "Other record"}])
def test_topic_alone_never_unlocks_hidden_record(change):
    body = request()
    body["requests"][0].update(change)
    assert not acquisition(body, LABEL)["acquired"]


def test_absent_inventory_or_ambiguous_priority_releases_nothing():
    assert not acquisition(request(), {**LABEL, "followup": None})["acquired"]
    body = request()
    body["requests"].append(copy.deepcopy(body["requests"][0]))
    assert not acquisition(body, LABEL)["acquired"]
    assert not acquisition({**body, "requests": []}, LABEL)["acquired"]
