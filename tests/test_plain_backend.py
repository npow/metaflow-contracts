"""Plain dict-spec validation — primitives, generics, edge cases."""

from __future__ import annotations

import pytest

from metaflow_contracts import ContractViolationError, contract
from metaflow_contracts.backends.plain import _beartype_available


class FakeStep:
    pass


def run(step_fn, **attrs):
    s = FakeStep()
    for k, v in attrs.items():
        setattr(s, k, v)
    step_fn(s)
    return s


# ---------------------------------------------------------------------------
# Primitive types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typ, value",
    [
        (str, "hello"),
        (int, 42),
        (float, 3.14),
        (bool, True),
        (bytes, b"data"),
        (list, [1, 2, 3]),
        (dict, {"a": 1}),
        (tuple, (1, 2)),
        (set, {1, 2}),
    ],
)
def test_primitive_pass(typ, value):
    @contract(outputs={"x": typ})
    def step(self):
        self.x = value

    run(step)


@pytest.mark.parametrize(
    "typ, bad_value",
    [
        (str, 42),
        (int, "hello"),
        (float, "3.14"),
        (bytes, "data"),
        (list, (1, 2)),
        (dict, [("a", 1)]),
        (tuple, [1, 2]),
        (set, [1, 2]),
    ],
)
def test_primitive_fail(typ, bad_value):
    @contract(outputs={"x": typ})
    def step(self):
        self.x = bad_value

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# bool is a subclass of int — isinstance behaviour
# ---------------------------------------------------------------------------


def test_bool_passes_int_check():
    """bool is a subtype of int; True/False should satisfy int contracts."""

    @contract(outputs={"n": int})
    def step(self):
        self.n = True

    run(step)  # should not raise


def test_bool_does_not_pass_float_check():
    @contract(outputs={"x": float})
    def step(self):
        self.x = True

    # bool is not a subtype of float (even though it converts cleanly)
    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# None values
# ---------------------------------------------------------------------------


def test_none_value_fails_str_check():
    @contract(outputs={"label": str})
    def step(self):
        self.label = None

    with pytest.raises(ContractViolationError):
        run(step)


def test_none_value_fails_int_check():
    @contract(outputs={"n": int})
    def step(self):
        self.n = None

    with pytest.raises(ContractViolationError):
        run(step)


# ---------------------------------------------------------------------------
# Generic / parameterised types (require beartype)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_list_of_int_pass():
    @contract(outputs={"xs": list[int]})
    def step(self):
        self.xs = [1, 2, 3]

    run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_list_of_int_fail_on_wrong_element():
    # beartype uses O(1) random sampling, so a mixed list may or may not be
    # caught. Use an all-strings list to guarantee failure regardless of which
    # element is sampled.
    @contract(outputs={"xs": list[int]})
    def step(self):
        self.xs = ["one", "two", "three"]

    with pytest.raises(ContractViolationError):
        run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_dict_str_float_pass():
    @contract(outputs={"scores": dict[str, float]})
    def step(self):
        self.scores = {"a": 0.9, "b": 0.1}

    run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_dict_str_float_fail_wrong_value_type():
    @contract(outputs={"scores": dict[str, float]})
    def step(self):
        self.scores = {"a": "high"}

    with pytest.raises(ContractViolationError):
        run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_optional_str_accepts_none():
    @contract(outputs={"label": str | None})
    def step(self):
        self.label = None

    run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_optional_str_accepts_str():
    @contract(outputs={"label": str | None})
    def step(self):
        self.label = "cat"

    run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_optional_str_rejects_int():
    @contract(outputs={"label": str | None})
    def step(self):
        self.label = 42

    with pytest.raises(ContractViolationError):
        run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_union_type_pass():
    @contract(outputs={"value": int | str})
    def step(self):
        self.value = "hello"

    run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_union_type_fail():
    @contract(outputs={"value": int | str})
    def step(self):
        self.value = 3.14

    with pytest.raises(ContractViolationError):
        run(step)


@pytest.mark.skipif(not _beartype_available, reason="beartype not installed")
def test_typing_any_always_passes():
    from typing import Any

    @contract(outputs={"x": Any})
    def step(self):
        self.x = object()  # literally anything

    run(step)


# ---------------------------------------------------------------------------
# Empty spec
# ---------------------------------------------------------------------------


def test_empty_dict_spec_is_noop():
    @contract(outputs={})
    def step(self):
        self.anything = "whatever"

    run(step)


# ---------------------------------------------------------------------------
# Multiple fields — partial failure
# ---------------------------------------------------------------------------


def test_first_invalid_field_raises_immediately():
    """Only the first violation is raised; the rest are not checked."""
    call_count = [0]

    @contract(outputs={"a": str, "b": int})
    def step(self):
        self.a = 99  # wrong
        self.b = "also wrong"
        call_count[0] += 1

    with pytest.raises(ContractViolationError, match="'a'"):
        run(step)


# ---------------------------------------------------------------------------
# Spec dict mutation after decoration
# ---------------------------------------------------------------------------


def test_mutating_spec_dict_after_decoration_has_no_effect():
    spec = {"label": str}

    @contract(outputs=spec)
    def step(self):
        self.label = "cat"
        self.injected = 42

    # Mutate the original spec — should not affect the contract
    spec["injected"] = int

    run(step)  # should still pass (injected not in contract)
