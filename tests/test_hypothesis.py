"""Property-based tests using Hypothesis."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from metaflow_contracts import ContractViolationError, contract


class FakeStep:
    pass


def run(step_fn, **attrs):
    s = FakeStep()
    for k, v in attrs.items():
        setattr(s, k, v)
    step_fn(s)
    return s


# ---------------------------------------------------------------------------
# Any valid value of the correct type should always pass
# ---------------------------------------------------------------------------


@given(st.text())
def test_str_always_passes_str_contract(value):
    @contract(outputs={"x": str})
    def step(self):
        self.x = value

    run(step)


@given(st.integers())
def test_int_always_passes_int_contract(value):
    @contract(outputs={"x": int})
    def step(self):
        self.x = value

    run(step)


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_float_always_passes_float_contract(value):
    @contract(outputs={"x": float})
    def step(self):
        self.x = value

    run(step)


@given(st.binary())
def test_bytes_always_passes_bytes_contract(value):
    @contract(outputs={"x": bytes})
    def step(self):
        self.x = value

    run(step)


@given(st.lists(st.integers()))
def test_list_always_passes_list_contract(value):
    @contract(outputs={"xs": list})
    def step(self):
        self.xs = value

    run(step)


@given(st.dictionaries(st.text(), st.integers()))
def test_dict_always_passes_dict_contract(value):
    @contract(outputs={"d": dict})
    def step(self):
        self.d = value

    run(step)


# ---------------------------------------------------------------------------
# Wrong types always fail
# ---------------------------------------------------------------------------


@given(st.integers())
def test_int_always_fails_str_contract(value):
    @contract(outputs={"x": str})
    def step(self):
        self.x = value

    with pytest.raises(ContractViolationError):
        run(step)


@given(st.text())
def test_str_always_fails_int_contract(value):
    @contract(outputs={"x": int})
    def step(self):
        self.x = value

    with pytest.raises(ContractViolationError):
        run(step)


@given(st.text())
def test_str_always_fails_list_contract(value):
    @contract(outputs={"x": list})
    def step(self):
        self.x = value

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Input contract: correct type passes, wrong type fails
# ---------------------------------------------------------------------------


@given(st.integers())
def test_int_input_passes(value):
    @contract(inputs={"n": int})
    def step(self):
        pass

    run(step, n=value)


@given(st.text())
def test_str_as_int_input_fails(value):
    @contract(inputs={"n": int})
    def step(self):
        pass

    with pytest.raises(ContractViolationError):
        run(step, n=value)


# ---------------------------------------------------------------------------
# Multiple fields: all must be correct
# ---------------------------------------------------------------------------


@given(st.text(), st.integers(), st.floats(allow_nan=False, allow_infinity=False))
def test_multiple_fields_all_correct(s, n, f):
    @contract(outputs={"s": str, "n": int, "f": float})
    def step(self):
        self.s = s
        self.n = n
        self.f = f

    run(step)


# ---------------------------------------------------------------------------
# Pydantic round-trip
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pytest.importorskip("pydantic", reason="pydantic not installed"),
    reason="pydantic not installed",
)
@given(st.text(), st.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=50)
def test_pydantic_roundtrip(label, confidence):
    from pydantic import BaseModel

    class Output(BaseModel):
        label: str
        confidence: float

    @contract(outputs=Output)
    def step(self):
        self.label = label
        self.confidence = confidence

    run(step)
