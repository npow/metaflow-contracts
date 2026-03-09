from __future__ import annotations

import functools
from typing import Any

from .backends import is_pydantic_model, validate_plain, validate_pydantic

# A contract spec is either a dict of {field: type} or a Pydantic BaseModel class.
Spec = dict[str, Any] | type

# Metaflow copies these attributes onto decorated step functions.
_METAFLOW_ATTRS = ("is_step", "_base_func", "decorators", "name")


def contract(
    outputs: Spec | None = None,
    inputs: Spec | None = None,
) -> Any:
    """
    Validate Metaflow step artifacts against a contract.

    Args:
        outputs: Primary pattern. Dict of ``{artifact_name: type}`` or a
                 Pydantic ``BaseModel`` subclass. Validated *after* the step
                 runs. Use this to catch bugs at the source.
        inputs:  Defensive pattern. Same format as ``outputs``. Validated
                 *before* the step runs. Use when consuming artifacts from
                 steps you don't own (e.g. third-party flows, fan-in joins).

    Raises:
        ContractViolationError: When an artifact is missing or has the wrong type.
        TypeError: When the spec is not a dict or Pydantic BaseModel.

    Example::

        @step
        @contract(outputs={"label": str, "confidence": float})
        def classify(self):
            self.label, self.confidence = model.predict(self.scores)
            self.next(self.end)
    """
    # Eagerly validate the specs so misconfiguration is caught at import time,
    # not at runtime inside a long pipeline run.
    if inputs is not None:
        _assert_valid_spec(inputs, "inputs")
    if outputs is not None:
        _assert_valid_spec(outputs, "outputs")

    # Copy dicts so later mutation of the caller's dict doesn't affect the contract.
    inputs_spec = dict(inputs) if isinstance(inputs, dict) else inputs
    outputs_spec = dict(outputs) if isinstance(outputs, dict) else outputs

    def decorator(step_func: Any) -> Any:
        @functools.wraps(step_func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            step_name = step_func.__name__

            if inputs_spec is not None:
                _validate(self, inputs_spec, phase="input", step_name=step_name)

            result = step_func(self, *args, **kwargs)

            if outputs_spec is not None:
                _validate(self, outputs_spec, phase="output", step_name=step_name)

            return result

        # Preserve Metaflow step metadata so the framework still recognises
        # the method as a step after we wrap it.
        for attr in _METAFLOW_ATTRS:
            if hasattr(step_func, attr):
                setattr(wrapper, attr, getattr(step_func, attr))

        return wrapper

    return decorator


def _validate(flow_self: Any, spec: Spec, phase: str, step_name: str) -> None:
    if is_pydantic_model(spec):
        validate_pydantic(flow_self, spec, phase=phase, step_name=step_name)
    else:
        validate_plain(flow_self, spec, phase=phase, step_name=step_name)  # type: ignore[arg-type]


def _assert_valid_spec(spec: Any, name: str) -> None:
    if not (isinstance(spec, dict) or is_pydantic_model(spec)):
        raise TypeError(
            f"Contract '{name}' must be a dict or Pydantic BaseModel subclass, "
            f"got {type(spec).__name__!r}"
        )
