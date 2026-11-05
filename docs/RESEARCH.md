# Research and defensible differentiation

Reviewed 5 November 2026. Public claims below are not independent audits of vendors. A feature not established by these sources is **unknown**, not evidence that a competitor lacks it.

## Commercial and native alternatives

| Reference | Publicly established capabilities | Implication for VERDICT |
|---|---|---|
| [Chargeflow integrations](https://docs.chargeflow.io/docs/reference/integrations), [API](https://docs.chargeflow.io/) | Processor integrations including PayPal, dispute intake, transaction/order matching, evidence enrichment and generated evidence. | Evidence collection and AI response preparation are commonplace; neither is a novelty claim. The reviewed pages do not establish our particular hypothesis-to-witness UI and reassessment record. |
| [Chargehound terms](https://www.chargehound.com/terms), [support](https://www.chargehound.com/support), [PayPal Q2 2021 release](https://s205.q4cdn.com/875401827/files/doc_financials/2021/q2/Q2-21-PayPal-Earnings-Release.pdf) | Chargehound identifies itself as a PayPal subsidiary. PayPal reported acquiring it in 2021 for dispute-management automation. Its support describes automated chargeback handling after purchase. | Do not market ordinary PayPal dispute automation as missing from PayPal's ecosystem. |
| [Disputely](https://www.disputely.com/), [automations](https://www.disputely.com/automations) | Publicly advertises PayPal and other integrations, prevention alerts, recovery, connected automations and activity logging. | Workflow automation, logs and cross-platform integration are established capabilities. We have not independently tested those commercial integrations. |
| [PayPal integration comparison](https://developer.paypal.com/disputes/choose-integration) | Resolution Center supports manual dispute handling; the API supports integrated automation. | A dashboard, evidence submission or buyer messaging alone adds little differentiation. |

## Closest open-source projects: source review

All commit IDs identify the inspected snapshot. No application source from these projects was copied into VERDICT. Design observations are attributed here; actual third-party dependencies remain in their package distributions with their licenses.

| Project and inspected commit | Source and tests inspected | Decision |
|---|---|---|
| [Dispute Desk](https://github.com/anishonly121/dispute-desk/tree/e483708192ce06c8c0e5b5c90c04bb9b8b87d5c4), MIT | `src/lib/approval.ts`, `approval.test.ts`, `paypal/disputes.ts`, `paypal/webhooks.ts`, LICENSE. Snapshot revalidation, serialized reservations, uncertain outcomes, tracking multipart input and provider signature verification are concrete implementations. | Adopt these operational principles in an original Python adapter. Especially preserve an unknown outcome instead of retrying. It is already a close PayPal copilot; do not fork/rename it or claim approval binding as novel. |
| [Dispute Agent](https://github.com/opensyndicate/dispute-agent/tree/b231843853633d27015661a644ac128334f73c02), MIT | `models.py`, `caseengine.py`, `reasons.py`, test tree and LICENSE. Deterministic evidence-kind scoring, critical gaps and reason specifications; mapping sources reference Stripe/card-network categories. | Reuse the separation of deterministic rules from generated prose as a design pattern. Do not import card-network reason rules or weighted fight thresholds into PayPal procedures. Avoid presence-of-document implying delivery correctness. |
| [DisputeShield](https://github.com/sahiti-veeravalli/DisputeSheild/tree/8e663ae884ca1287d4ea0d578d676ec387753a8f), MIT | Java `EvidenceRules.java`, frontend `InvestigationWorkspace.tsx`, authentication/RBAC test locations and LICENSE. Source includes rule-driven evidence readiness and dashboard workflows. | Useful UX and role-separation precedent. Build our own graph/data binding; do not reuse generated context values as independently validated records. |
| [DisputeLens](https://github.com/mitali-gautam05/DisputeLens/tree/b194c514b5f1fd4d69f9518b236e1893eefa1add), no license file found in inspected tree | `backend/src/agent.py`, `retrieve_and_generate.py`, requirements/tree. The agent can retrieve more *similar historical cases*, escalate to humans or finalize a cited response with a bounded loop. | Research only, no code reuse. Its agentic retrieval means “asks for more evidence” is already prior art. Distinguish acquiring a new case-specific witness from retrieving precedents; neither concept is claimed as our invention. |
| [Dispute Pilot](https://github.com/vyayasan/dispute-pilot/tree/7047af4ef7d3e95b17c3e18359d0efa219749ae0), MIT | `approval/approval.ts`, `agent/guardrails.ts`, red-team approval tests and LICENSE. Approvals bind financial state, evidence hashes, policy, nonce and expiry; tests alter fields and check replay. | Use the rigor as precedent. Our durable server approval records bind exact payload and case/provider snapshots. We do not claim hashes establish truth or transplant Airwallex's state model into PayPal. |

### Additional toolkit audit

- [Docling](https://github.com/docling-project/docling): document conversion and layout parsing, MIT project with separately licensed model artifacts. Valuable for OCR/tables; deferred to avoid model downloads and infrastructure before evidence types demand it. Initial parsing uses BSD-licensed pypdf, with page provenance and explicit no-OCR limits.
- [LangGraph](https://github.com/langchain-ai/langgraph): MIT orchestration, persistence and human interrupts. Useful when execution becomes long-running. A bounded two-call analysis plus transactional application state is sufficient at this stage; no autonomous tools or swarm.
- [Graphiti](https://github.com/getzep/graphiti): Apache-2.0 temporal knowledge graph infrastructure. Deferred because its additional graph service/model dependencies do not solve our core source-support problem automatically. Typed case records and claim relationships are adequate for bounded cases.
- [React Flow](https://github.com/xyflow/xyflow): MIT React node/edge interaction; **integrated**, preserving attribution. Evidence→claim citations and claim→hypothesis relations come from persisted analysis, not decorative data.
- [DeepEval](https://github.com/confident-ai/deepeval): Apache-2.0 evaluation framework. Its judge-based metrics are useful, but cannot create independent truth labels. Initial reproducible harness uses pytest plus authored case labels and an explicit model-assessed entailment metric, avoiding a second evaluation framework and its provider configuration.
- [PayPal API reference](https://developer.paypal.com/api/customer-disputes/v1): use REST directly with the existing httpx stack; no assumption that a generic payments SDK covers every dispute endpoint.

## Academic grounding

[ALCE (EMNLP 2023)](https://arxiv.org/abs/2305.14627) separates citation quality from answer correctness and supports measuring semantic entailment, not merely finding a quotation. VERDICT's exact substring check and separate model support review follow that distinction; our reviewer is not a calibrated independent verifier.

[From Passive to Active Reasoning (2025)](https://arxiv.org/abs/2506.08295) studies asking for missing information rather than answering only from the initial context. [Uncertainty of Thoughts](https://arxiv.org/pdf/2402.03271) explores uncertainty-aware question planning. These are research precedents, not empirical evidence that our financial-dispute workflow improves outcomes. VERDICT uses qualitative discriminative questions, not computed Bayesian information gain or calibrated probabilities.

## Current hackathon overlap

Public project pages already advertise [Dispute Defender](https://devpost.com/software/dispute-defender), [Rebuttal](https://devpost.com/software/rebuttal-u5njti), [Culpa](https://devpost.com/software/culpa) and [Subguard](https://github.com/StuartYo/subguard). These are self-descriptions, not validated performance. Seller Shield's Discord announcement is user-provided context; its current capabilities were not independently verified. VERDICT is not the only dispute project.

## What we can responsibly say

VERDICT combines two-sided case records, source inspection, competing hypotheses, a request that names what it distinguishes, restricted witness acquisition, and before/after reassessment with a PayPal-aware human review boundary. This integration and interface are our original implementation. Existing frameworks, prior dispute assistants and active-reasoning work are acknowledged.

**Unproven hypotheses:** that our request policy beats a careful ordinary LLM; that merchants or buyers find it more usable; that it improves real PayPal outcomes. The development benchmark must report ties, failures and baseline wins. No first-ever, unbiased, fraud-proof, production-ready, automated truth or win-rate claim is justified.
