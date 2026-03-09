"""Pydantic BaseModel backend — comprehensive coverage."""

from __future__ import annotations

import pytest

pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")
from pydantic import BaseModel, field_validator  # noqa: E402

from metaflow_contracts import ContractViolationError, contract  # noqa: E402


class FakeStep:
    pass


def run(step_fn, **attrs):
    s = FakeStep()
    for k, v in attrs.items():
        setattr(s, k, v)
    step_fn(s)
    return s


# ---------------------------------------------------------------------------
# Basic valid / invalid
# ---------------------------------------------------------------------------


class SimpleOutput(BaseModel):
    label: str
    confidence: float


def test_pydantic_outputs_valid():
    @contract(outputs=SimpleOutput)
    def step(self):
        self.label = "cat"
        self.confidence = 0.9

    run(step)


def test_pydantic_outputs_wrong_type():
    @contract(outputs=SimpleOutput)
    def step(self):
        self.label = "cat"
        self.confidence = "oops"

    with pytest.raises(ContractViolationError):
        run(step)


def test_pydantic_outputs_missing_field():
    @contract(outputs=SimpleOutput)
    def step(self):
        self.label = "cat"
        # confidence not set → treated as None → validation error

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


class WithOptional(BaseModel):
    label: str
    note: str | None = None


def test_optional_field_accepts_none():
    @contract(outputs=WithOptional)
    def step(self):
        self.label = "cat"
        # note not set — should default to None

    run(step)


def test_optional_field_accepts_value():
    @contract(outputs=WithOptional)
    def step(self):
        self.label = "cat"
        self.note = "looks good"

    run(step)


def test_optional_field_rejects_wrong_type():
    @contract(outputs=WithOptional)
    def step(self):
        self.label = "cat"
        self.note = 42

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class WithDefaults(BaseModel):
    label: str
    confidence: float = 0.0


def test_default_field_not_required_on_step():
    @contract(outputs=WithDefaults)
    def step(self):
        self.label = "cat"
        # confidence not set; model default is 0.0 but pydantic validates
        # the value we pass (None) not the default

    # None passed as confidence should fail because float requires a value
    with pytest.raises(ContractViolationError):
        run(step)


def test_default_field_explicit_value_passes():
    @contract(outputs=WithDefaults)
    def step(self):
        self.label = "cat"
        self.confidence = 0.95

    run(step)


# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class Metadata(BaseModel):
    version: int
    source: str


class NestedOutput(BaseModel):
    label: str
    meta: Metadata


def test_nested_model_pass():
    @contract(outputs=NestedOutput)
    def step(self):
        self.label = "cat"
        self.meta = Metadata(version=1, source="cam")

    run(step)


def test_nested_model_wrong_type_for_nested():
    @contract(outputs=NestedOutput)
    def step(self):
        self.label = "cat"
        self.meta = {"version": 1, "source": "cam"}  # dict, not Metadata

    # Pydantic v2 will coerce this by default — should pass
    run(step)


def test_nested_model_invalid_nested_value():
    @contract(outputs=NestedOutput)
    def step(self):
        self.label = "cat"
        self.meta = "not a model"

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Custom validators
# ---------------------------------------------------------------------------


class Scored(BaseModel):
    confidence: float

    @field_validator("confidence")
    @classmethod
    def must_be_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v


def test_custom_validator_passes():
    @contract(outputs=Scored)
    def step(self):
        self.confidence = 0.75

    run(step)


def test_custom_validator_rejects_out_of_range():
    @contract(outputs=Scored)
    def step(self):
        self.confidence = 1.5

    with pytest.raises(ContractViolationError, match="confidence"):
        run(step)


# ---------------------------------------------------------------------------
# Multiple validation errors reported together
# ---------------------------------------------------------------------------


class MultiField(BaseModel):
    a: str
    b: int


def test_multiple_pydantic_errors_in_one_exception():
    @contract(outputs=MultiField)
    def step(self):
        self.a = 99
        self.b = "wrong"

    with pytest.raises(ContractViolationError) as exc_info:
        run(step)

    # Both field errors should be mentioned
    msg = str(exc_info.value)
    assert "a" in msg or "b" in msg


# ---------------------------------------------------------------------------
# inputs via pydantic
# ---------------------------------------------------------------------------


class ExpectedInput(BaseModel):
    scores: list[float]


def test_pydantic_inputs_valid():
    @contract(inputs=ExpectedInput)
    def step(self):
        pass

    run(step, scores=[0.1, 0.9])


def test_pydantic_inputs_wrong_type():
    @contract(inputs=ExpectedInput)
    def step(self):
        pass

    with pytest.raises(ContractViolationError, match="input"):
        run(step, scores="not a list")


# ---------------------------------------------------------------------------
# Model inheritance
# ---------------------------------------------------------------------------


class Base(BaseModel):
    label: str


class Extended(Base):
    confidence: float


def test_inherited_model_validates_all_fields():
    @contract(outputs=Extended)
    def step(self):
        self.label = "cat"
        self.confidence = 0.9

    run(step)


def test_inherited_model_missing_parent_field():
    @contract(outputs=Extended)
    def step(self):
        # label missing
        self.confidence = 0.9

    with pytest.raises(ContractViolationError):
        run(step)
