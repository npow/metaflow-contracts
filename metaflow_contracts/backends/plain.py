from __future__ import annotations

from typing import Any

from ..errors import ContractViolationError

try:
    from beartype.door import is_bearable

    _beartype_available = True
except ImportError:
    _beartype_available = False

_MISSING = object()


def _type_name(t: Any) -> str:
    return getattr(t, "__name__", None) or repr(t)


def _check(value: Any, expected_type: Any) -> bool:
    if _beartype_available:
        return bool(is_bearable(value, expected_type))
    return isinstance(value, expected_type)


def validate_plain(
    flow_self: Any,
    spec: dict[str, Any],
    phase: str,
    step_name: str,
) -> None:
    for field, expected_type in spec.items():
        value = getattr(flow_self, field, _MISSING)
        if value is _MISSING:
            raise ContractViolationError(
                step_name,
                phase,
                f"'{field}' is missing (expected {_type_name(expected_type)})",
            )
        if not _check(value, expected_type):
            raise ContractViolationError(
                step_name,
                phase,
                f"'{field}' expected {_type_name(expected_type)}, "
                f"got {type(value).__name__}",
            )
