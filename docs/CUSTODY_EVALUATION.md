# Custody-aware development pilot — 6 November 2026

**Decision: retain the production baseline.** This experiment improves acquisition measurement but does not establish an acquisition advantage. The original 30-case 28/30 checklist–VERDICT tie and raw outputs remain unchanged.

The protocol, prompts, schema, input hashes and runner/product-source hashes were frozen in [protocol.json](../evaluation/custody-pilot/protocol.json) before calls. Eight cases were selected using prior development knowledge: F01, F09, F10, F15, F21, F24, F27 and F30. This is not a held-out evaluation. There were 25 completed analyses, each using real generation plus semantic-support review, and zero recorded failures. Execution was serial and checkpointed.

Both strategies received the same custody fields and processing. Requests distinguish the recipient from the original record custodian, specify a direct/forwarded/unknown route and state availability uncertainty. A seller forwarding a carrier record is allowed; calling the seller that record's original custodian is not. The simulated oracle requires one first request, a topic match, the authored custodian, a valid route, a referenced hypothesis and available fictional inventory. Topic matches alone release nothing. Responses remain origin-unverified. No external record-acquisition integration was created by this experiment.

| Measure | Checklist B | Experimental VERDICT |
|---|---:|---:|
| Initial authored finding matches | 7/8 | 8/8 |
| Own acquired records / eligible inventories | 3/6 | 3/6 |
| Final authored finding matches, all eight cases | 6/8 | 8/8 |
| Finding matches on the same V-acquired evidence | 3/3 | 3/3 |
| Requests on the two stop cases | 0 | 0 |
| Initial claims assessed nonentailed by the model | 0/18 | 0/19 |

Both acquired F01, F09 and F27 records. Both failed the custody gate on F10, F15 and F21: requests sought broadly relevant material from a buyer/seller but did not identify the inventory's authored independent technician or payment provider as custodian. A gate failure does not prove the request useless; it prevents granting a different hidden record just because the topic matches. These cases need independently reviewed, multiple-valid-route labels.

The final finding difference combines initial reasoning and information availability; it does not isolate an active-acquisition effect. The matched-evidence comparison ties. Eight authored cases, imperfect regex topics, one-author custody labels and model-assessed entailment cannot establish superiority, calibrated accuracy or real outcomes. Availability assertions have not been independently scored. Latency/token counts remain in raw outputs; no cost reduction is claimed.

[Raw outputs/gates](../evaluation/custody-pilot/results.json) · [Summary](../evaluation/custody-pilot/summary.json) · [Runner](../evaluation/custody_pilot.py)

Run `backend/.venv/Scripts/python.exe evaluation/custody_pilot.py run` to reuse completed checkpoints. Changed protocol inputs/code and silently discarded failures are refused. Use `report` to summarize without new calls. A new experiment needs a separate directory and frozen protocol. Trusted Python experiment hooks cannot be selected through the HTTP API. Production schema/prompt defaults are unchanged.

Next: independently label acceptable record types, custodians, routes, burden and availability; freeze a separate held-out set; compare equal acquisition budgets and matched evidence; audit claims and request usefulness with human raters. Do not promote on this pilot alone.
