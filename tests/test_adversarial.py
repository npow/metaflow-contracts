"""Adversarial and edge-case tests."""

from __future__ import annotations

import pytest

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
# Properties that raise on access
# ---------------------------------------------------------------------------


class StepWithBadProperty:
    @property
    def scores(self):
        raise RuntimeError("intentional property error")


def test_input_property_raises_propagates():
    """If reading an artifact raises, the original exception should propagate,
    not be swallowed into a ContractViolationError."""

    @contract(inputs={"scores": list})
    def step(self):
        pass

    with pytest.raises(RuntimeError, match="intentional"):
        step(StepWithBadProperty())


# ---------------------------------------------------------------------------
# Stacking multiple @contract decorators
# ---------------------------------------------------------------------------


def test_stacked_contracts_both_pass():
    @contract(outputs={"a": str})
    @contract(outputs={"b": int})
    def step(self):
        self.a = "hello"
        self.b = 1

    run(step)


def test_stacked_contracts_outer_fails():
    @contract(outputs={"a": str})
    @contract(outputs={"b": int})
    def step(self):
        self.a = 99  # wrong — outer contract catches this
        self.b = 1

    with pytest.raises(ContractViolationError):
        run(step)


def test_stacked_contracts_inner_fails():
    @contract(outputs={"a": str})
    @contract(outputs={"b": int})
    def step(self):
        self.a = "hello"
        self.b = "wrong"  # inner contract catches this

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Non-standard field names
# ---------------------------------------------------------------------------


def test_field_name_that_is_a_python_builtin():
    """Using a name like 'type' or 'id' as an artifact — should still work."""

    @contract(outputs={"id": int})
    def step(self):
        self.id = 42

    run(step)


def test_field_name_with_underscore_prefix():
    @contract(outputs={"_private": str})
    def step(self):
        self._private = "ok"

    run(step)


# ---------------------------------------------------------------------------
# Very large number of fields
# ---------------------------------------------------------------------------


def test_many_fields_all_valid():
    spec = {f"field_{i}": int for i in range(50)}

    @contract(outputs=spec)
    def step(self):
        for i in range(50):
            setattr(self, f"field_{i}", i)

    run(step)


def test_many_fields_last_one_wrong():
    spec = {f"field_{i}": int for i in range(50)}

    @contract(outputs=spec)
    def step(self):
        for i in range(50):
            setattr(self, f"field_{i}", i)
        self.field_49 = "wrong"

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# NaN and Inf as float values
# ---------------------------------------------------------------------------


def test_nan_passes_float_contract():
    import math

    @contract(outputs={"x": float})
    def step(self):
        self.x = float("nan")

    s = run(step)
    assert math.isnan(s.x)


def test_inf_passes_float_contract():
    @contract(outputs={"x": float})
    def step(self):
        self.x = float("inf")

    run(step)


# ---------------------------------------------------------------------------
# Empty string field value
# ---------------------------------------------------------------------------


def test_empty_string_passes_str_contract():
    @contract(outputs={"label": str})
    def step(self):
        self.label = ""

    run(step)


# ---------------------------------------------------------------------------
# Contract on non-Metaflow (plain) function
# ---------------------------------------------------------------------------


def test_contract_works_on_plain_function():
    """@contract should work on any callable, not just Metaflow steps."""

    @contract(outputs={"result": int})
    def compute(self):
        self.result = 42

    s = FakeStep()
    compute(s)
    assert s.result == 42


# ---------------------------------------------------------------------------
# Re-using the same contract on multiple steps
# ---------------------------------------------------------------------------


def test_shared_contract_instance():
    shared = contract(outputs={"x": int})

    @shared
    def step_a(self):
        self.x = 1

    @shared
    def step_b(self):
        self.x = 2

    run(step_a)
    run(step_b)


def test_shared_contract_one_step_fails():
    shared = contract(outputs={"x": int})

    @shared
    def step_a(self):
        self.x = 1

    @shared
    def step_bad(self):
        self.x = "oops"

    run(step_a)
    with pytest.raises(ContractViolationError):
        run(step_bad)


# ---------------------------------------------------------------------------
# Artifact set to None explicitly vs never set
# ---------------------------------------------------------------------------


def test_none_vs_missing_distinction():
    """An attribute set to None is different from never being set.
    Both should fail a str contract, but the error message should differ."""
    step_none_msg = None
    step_missing_msg = None

    @contract(outputs={"x": str})
    def step_none(self):
        self.x = None

    @contract(outputs={"x": str})
    def step_missing(self):
        pass

    try:
        run(step_none)
    except ContractViolationError as e:
        step_none_msg = str(e)

    try:
        run(step_missing)
    except ContractViolationError as e:
        step_missing_msg = str(e)

    assert step_none_msg is not None
    assert step_missing_msg is not None
    assert "missing" in step_missing_msg
    assert "missing" not in step_none_msg


# ---------------------------------------------------------------------------
# Inputs validated before step body runs (timing guarantee)
# ---------------------------------------------------------------------------


def test_input_validation_runs_before_step_body():
    side_effects = []

    @contract(inputs={"x": int})
    def step(self):
        side_effects.append("ran")

    with pytest.raises(ContractViolationError):
        run(step, x="not int")

    assert side_effects == [], "Step body must not run when input validation fails"


# ---------------------------------------------------------------------------
# Output validation runs after step body completes (timing guarantee)
# ---------------------------------------------------------------------------


def test_output_validation_runs_after_step_body():
    side_effects = []

    @contract(outputs={"x": int})
    def step(self):
        side_effects.append("ran")
        self.x = "wrong"

    with pytest.raises(ContractViolationError):
        run(step)

    assert side_effects == ["ran"], "Step body must complete before output validation"
