"""Pydantic data contracts shared by every module."""
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
LLMFindingType = Literal["contradiction", "missing_requirement", "incomplete_enumeration", "untestable"]
FindingType = Literal[
    "contradiction", "missing_requirement", "incomplete_enumeration", "untestable",
    "orphan_trace", "invalid_enum_value", "no_test", "test_unknown_req",
]


class Requirement(BaseModel):
    id: str = Field(pattern=r"^NP-REQ-\d{3}$")
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    feature: str = Field(min_length=1)
    modes: list[str] = []
    profiles: list[str] = []
    traces_to: str | None = Field(default=None, pattern=r"^NP-SYS-\d{3}$")
    measurable: bool


class ParseOut(BaseModel):
    requirements: list[Requirement] = Field(min_length=1)


class LLMFinding(BaseModel):
    type: LLMFindingType
    severity: Severity
    cited_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class AnalyzeOut(BaseModel):
    findings: list[LLMFinding]


class Finding(BaseModel):
    source: Literal["deterministic", "llm"]
    type: FindingType
    severity: Severity
    cited_ids: list[str] = Field(min_length=1)
    rationale: str


class DraftStepOut(BaseModel):
    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    traces_to: list[str] = Field(min_length=1)
    legacy_step: str | None = None  # set => reused from the legacy protocol


class RetiredOut(BaseModel):
    legacy_step: str
    reason: str = Field(min_length=1)


class DraftOut(BaseModel):
    steps: list[DraftStepOut] = Field(min_length=1)
    retired: list[RetiredOut] = []


class LegacyStep(BaseModel):
    step: str
    description: str
    action: str
    expected_result: str
    traces_to: str


class Step(BaseModel):
    id: str
    feature: str
    action: str
    expected_result: str
    traces_to: list[str]
    origin: Literal["reused", "new"]
    legacy_step: str | None = None
