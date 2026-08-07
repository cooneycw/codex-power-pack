"""Typed models for skill evaluation inputs and safe result summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Category(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    NEGATIVE = "negative"
    INCOMPLETE = "incomplete"
    EDGE = "edge"


class Lane(str, Enum):
    DETERMINISTIC = "deterministic"
    LIVE = "live"


class Outcome(str, Enum):
    UNAVAILABLE = "unavailable"
    ACTIVATION_FAILURE = "activation_failure"
    PROCEDURE_FAILURE = "procedure_failure"
    RUNTIME_FAILURE = "runtime_failure"
    OUTPUT_FAILURE = "output_failure"
    PASS = "pass"


class ContractLayer(str, Enum):
    UNAVAILABLE = "unavailable"
    ROUTING = "routing"
    PROCEDURE = "procedure"
    ARTIFACT = "artifact"
    PARSER = "parser"
    GROUPING = "grouping"
    ISSUE_BODY = "issue-body"
    MAPPING = "mapping"
    RUNTIME = "runtime"
    OUTPUT = "output"


@dataclass(frozen=True)
class Expectation:
    selected_skill: str | None
    required_checkpoints: tuple[str, ...] = ()
    required_output_fields: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    skill: str | None
    category: Category
    prompt: str
    lanes: tuple[Lane, ...]
    tags: tuple[str, ...]
    expectation: Expectation
    deterministic: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "skill": self.skill,
            "category": self.category.value,
            "prompt": self.prompt,
            "lanes": [lane.value for lane in self.lanes],
            "tags": list(self.tags),
            "expected": {
                "selected_skill": self.expectation.selected_skill,
                "required_checkpoints": list(self.expectation.required_checkpoints),
                "required_output_fields": list(self.expectation.required_output_fields),
                "forbidden_actions": list(self.expectation.forbidden_actions),
            },
            "deterministic": self.deterministic,
        }


@dataclass(frozen=True)
class LiveControls:
    timeout_seconds: int
    max_cases: int
    max_total_tokens: int
    max_output_bytes: int
    retention_days: int
    model: str | None = None


@dataclass(frozen=True)
class Thresholds:
    direct_recall: float
    indirect_recall: float
    negative_precision: float


@dataclass(frozen=True)
class EvaluationSuite:
    suite_id: str
    tracking_issue: int
    thresholds: Thresholds
    live_controls: LiveControls
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True)
class Observation:
    case_id: str
    available: bool = True
    activation_checked: bool = True
    selected_skill: str | None = None
    selected_skill_raw: str | None = None
    checkpoints: tuple[str, ...] = ()
    output_fields: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    contracts: dict[ContractLayer, bool] = field(default_factory=dict)
    exit_code: int = 0
    timed_out: bool = False
    runtime_error: str | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None
    summary: str = ""


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    skill: str | None
    category: Category
    lane: Lane
    outcome: Outcome
    contract_layer: ContractLayer | None
    reasons: tuple[str, ...]
    activation_checked: bool
    selected_skill_raw: str | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "skill": self.skill,
            "category": self.category.value,
            "lane": self.lane.value,
            "outcome": self.outcome.value,
            "contract_layer": self.contract_layer.value if self.contract_layer else None,
            "reasons": list(self.reasons),
            "activation_checked": self.activation_checked,
            "selected_skill_raw": self.selected_skill_raw,
            "latency_ms": self.latency_ms,
            "total_tokens": self.total_tokens,
        }
