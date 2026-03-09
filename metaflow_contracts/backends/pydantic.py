from __future__ import annotations

from typing import Any

from ..errors import ContractViolationError

_MISSING = object()


def is_pydantic_model(obj: Any) -> bool:
    try:
        from pydantic import BaseModel

        return isinstance(obj, type) and issubclass(obj, BaseModel)
    except ImportError:
        return False


def validate_pydantic(
    flow_self: Any,
    model_cls: type,
    phase: str,
    step_name: str,
) -> None:
    from pydantic import ValidationError

    fields = model_cls.model_fields
    data = {field: getattr(flow_self, field, _MISSING) for field in fields}
    # Replace _MISSING with None so pydantic sees absent required fields as null
    # (which will fail required-field validation with a clear message)
    coerced = {k: (None if v is _MISSING else v) for k, v in data.items()}

    try:
        model_cls.model_validate(coerced)
    except ValidationError as exc:
        details = "; ".join(f"'{err['loc'][0]}': {err['msg']}" for err in exc.errors())
        raise ContractViolationError(step_name, phase, details) from exc
