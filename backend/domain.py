from typing import Literal
from pydantic import BaseModel, Field, ConfigDict,field_validator
from decimal import Decimal,InvalidOperation
import re


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(StrictModel):
    id: str
    text: str = Field(max_length=700)
    source_id: str
    quote: str = Field(min_length=1, max_length=1500)
    subject: str = Field(max_length=100)
    field: str = Field(max_length=100)
    value: str = Field(max_length=300)
    stance: Literal["buyer", "seller", "neutral"]
    epistemic_status: Literal["party_report", "document_finding", "document_order", "current_policy", "uncertain"] = "uncertain"


class Hypothesis(StrictModel):
    id: str
    title: str = Field(max_length=200)
    explanation: str = Field(max_length=1000)
    supports: list[str] = Field(max_length=15)
    challenges: list[str] = Field(max_length=15)
    status: Literal["plausible", "supported", "weakened", "unresolved"]


class Witness(StrictModel):
    id: str
    title: str = Field(max_length=200)
    question: str = Field(max_length=1000)
    recipient: Literal["buyer", "seller", "carrier", "payment_provider", "other"]
    distinguishes: list[str] = Field(max_length=8)
    rationale: str = Field(max_length=1000)
    burden: Literal["low", "medium", "high"]
    priority: Literal["first", "next", "optional"]
    publicly_obtainable: bool = False
    public_research_query: str = Field(default="", max_length=600)


class Analysis(StrictModel):
    summary: str = Field(max_length=1500)
    finding: Literal["insufficient", "supports_buyer", "supports_seller", "conflicting"]
    claims: list[Claim] = Field(max_length=24)
    hypotheses: list[Hypothesis] = Field(max_length=8)
    requests: list[Witness] = Field(max_length=5)
    unknowns: list[str] = Field(max_length=12)
    recommendation: str = Field(max_length=1400)


class Support(StrictModel):
    claim_id: str
    support: Literal["entailed", "partial", "unsupported", "uncertain"]
    reason: str = Field(max_length=500)
    epistemic_status: Literal["party_report", "document_finding", "document_order", "current_policy", "uncertain"] = "uncertain"
    epistemic_reason: str = Field(default="", max_length=500)


class SupportReview(StrictModel):
    reviews: list[Support] = Field(max_length=24)


class EvidenceInput(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=30000)
    party: Literal["buyer", "seller", "carrier", "payment_provider", "other"] = "seller"


class CaseInput(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    reason: Literal[
        "ITEM_NOT_RECEIVED",
        "SIGNIFICANTLY_NOT_AS_DESCRIBED",
        "DUPLICATE_TRANSACTION",
        "CREDIT_NOT_PROCESSED",
        "OTHER",
    ] = "OTHER"
    amount: str = Field(pattern=r"^\d{1,9}\.\d{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator('amount',mode='before')
    @classmethod
    def normal_amount(cls,value):
        text=str(value).strip()
        if not re.fullmatch(r'(?:\d{1,9}|\d{1,3}(?:,\d{3}){1,2})(?:\.\d{1,2})?',text):raise ValueError('Enter an amount such as 12000 or 12000.00')
        try:return format(Decimal(text.replace(',','')).quantize(Decimal('.01')),'f')
        except InvalidOperation:raise ValueError('Enter a valid amount') from None


class AnalyzeInput(StrictModel):
    consent: bool = False


class ActionInput(StrictModel):
    action: Literal["send-message", "provide-evidence", "accept-claim"]
    note: str = Field(min_length=1, max_length=1200)
    evidence_type: Literal["PROOF_OF_FULFILLMENT", "OTHER"] = "PROOF_OF_FULFILLMENT"
    tracking_number: str = Field(default="", max_length=100)
    carrier: str = Field(default="", max_length=100)


class ExecuteInput(StrictModel):
    approval_id: str
    reviewed_digest: str
    confirmed: bool
