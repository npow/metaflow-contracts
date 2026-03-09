"""Core @contract decorator behaviour."""

from __future__ import annotations

import pytest

from metaflow_contracts import ContractViolationError, contract


class FakeStep:
    """Minimal stand-in for a Metaflow FlowSpec step."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(step_fn, **attrs):
    """Create a FakeStep, set attrs, call the step, return the step."""
    s = FakeStep()
    for k, v in attrs.items():
        setattr(s, k, v)
    step_fn(s)
    return s


# ---------------------------------------------------------------------------
# outputs - dict spec
# ---------------------------------------------------------------------------


def test_outputs_valid_single_field():
    @contract(outputs={"label": str})
    def step(self):
        self.label = "cat"

    run(step)


def test_outputs_valid_multiple_fields():
    @contract(outputs={"label": str, "confidence": float, "count": int})
    def step(self):
        self.label = "cat"
        self.confidence = 0.9
        self.count = 3

    run(step)


def test_outputs_wrong_type_raises():
    @contract(outputs={"label": str})
    def step(self):
        self.label = 42

    with pytest.raises(ContractViolationError, match="output"):
        run(step)


def test_outputs_missing_artifact_raises():
    @contract(outputs={"label": str})
    def step(self):
        pass  # forgot to set self.label

    with pytest.raises(ContractViolationError, match="missing"):
        run(step)


def test_outputs_none_value_on_non_optional_raises():
    @contract(outputs={"label": str})
    def step(self):
        self.label = None

    with pytest.raises(ContractViolationError):
        run(step)


def test_outputs_falsy_values_are_valid():
    """0, [], False are valid values for their respective types."""

    @contract(outputs={"n": int, "items": list, "flag": bool})
    def step(self):
        self.n = 0
        self.items = []
        self.flag = False

    run(step)


# ---------------------------------------------------------------------------
# inputs - dict spec
# ---------------------------------------------------------------------------


def test_inputs_valid():
    @contract(inputs={"scores": list})
    def step(self):
        pass

    run(step, scores=[1.0, 2.0])


def test_inputs_wrong_type_raises():
    @contract(inputs={"scores": list})
    def step(self):
        pass

    with pytest.raises(ContractViolationError, match="input"):
        run(step, scores="not a list")


def test_inputs_missing_raises():
    @contract(inputs={"scores": list})
    def step(self):
        pass

    with pytest.raises(ContractViolationError, match="missing"):
        run(step)  # no scores attribute


def test_inputs_failure_prevents_step_body_from_running():
    executed = []

    @contract(inputs={"x": int})
    def step(self):
        executed.append(True)

    with pytest.raises(ContractViolationError):
        run(step, x="wrong")

    assert executed == [], "Step body should not have run after input failure"


# ---------------------------------------------------------------------------
# both inputs and outputs
# ---------------------------------------------------------------------------


def test_inputs_and_outputs_both_valid():
    @contract(inputs={"raw": list}, outputs={"result": int})
    def step(self):
        self.result = len(self.raw)

    s = run(step, raw=[1, 2, 3])
    assert s.result == 3


def test_inputs_and_outputs_input_fails():
    @contract(inputs={"raw": list}, outputs={"result": int})
    def step(self):
        self.result = 0

    with pytest.raises(ContractViolationError, match="input"):
        run(step, raw="oops")


def test_inputs_and_outputs_output_fails():
    @contract(inputs={"raw": list}, outputs={"result": int})
    def step(self):
        self.result = "oops"

    with pytest.raises(ContractViolationError, match="output"):
        run(step, raw=[1, 2])


# ---------------------------------------------------------------------------
# no-op contracts
# ---------------------------------------------------------------------------


def test_no_contract_args_is_noop():
    @contract()
    def step(self):
        self.x = "anything"

    run(step)


def test_outputs_only_ignores_extra_attrs():
    @contract(outputs={"label": str})
    def step(self):
        self.label = "cat"
        self.uncontracted = 42  # not in spec, should be ignored

    run(step)


# ---------------------------------------------------------------------------
# exception safety
# ---------------------------------------------------------------------------


def test_step_exception_propagates_without_output_validation():
    """If the step raises, outputs must not be validated."""
    validated = []

    @contract(outputs={"label": str})
    def step(self):
        raise RuntimeError("step failed")

    s = FakeStep()
    with pytest.raises(RuntimeError):
        step(s)

    assert validated == []
    assert not hasattr(s, "label")


# ---------------------------------------------------------------------------
# decorator metadata preservation
# ---------------------------------------------------------------------------


def test_preserves_name():
    @contract(outputs={"x": int})
    def my_step(self):
        self.x = 1

    assert my_step.__name__ == "my_step"


def test_preserves_docstring():
    @contract(outputs={"x": int})
    def my_step(self):
        """This is the docstring."""
        self.x = 1

    assert my_step.__doc__ == "This is the docstring."


def test_preserves_wrapped():
    def my_step(self):
        self.x = 1

    wrapped = contract(outputs={"x": int})(my_step)
    assert wrapped.__wrapped__ is my_step


def test_preserves_metaflow_is_step_attr():
    def my_step(self):
        self.x = 1

    my_step.is_step = True
    wrapped = contract(outputs={"x": int})(my_step)
    assert wrapped.is_step is True


# ---------------------------------------------------------------------------
# invalid spec raises TypeError at decoration time
# ---------------------------------------------------------------------------


def test_invalid_spec_string_raises():
    with pytest.raises(TypeError, match="outputs"):

        @contract(outputs="not valid")
        def step(self):
            pass


def test_invalid_spec_int_raises():
    with pytest.raises(TypeError, match="inputs"):

        @contract(inputs=42)
        def step(self):
            pass


def test_invalid_spec_list_raises():
    with pytest.raises(TypeError):

        @contract(outputs=[str, int])
        def step(self):
            pass


# ---------------------------------------------------------------------------
# error message quality
# ---------------------------------------------------------------------------


def test_error_message_contains_step_name():
    @contract(outputs={"x": str})
    def my_custom_step(self):
        self.x = 99

    with pytest.raises(ContractViolationError, match="my_custom_step"):
        run(my_custom_step)


def test_error_message_contains_field_name():
    @contract(outputs={"confidence": float})
    def step(self):
        self.confidence = "oops"

    with pytest.raises(ContractViolationError, match="confidence"):
        run(step)


def test_error_attributes():
    @contract(outputs={"x": str})
    def step(self):
        self.x = 99

    s = FakeStep()
    try:
        step(s)
    except ContractViolationError as exc:
        assert exc.step == "step"
        assert exc.phase == "output"
        assert "x" in exc.detail
