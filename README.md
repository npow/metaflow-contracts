# metaflow-contracts

[![CI](https://github.com/npow/metaflow-contracts/actions/workflows/ci.yml/badge.svg)](https://github.com/npow/metaflow-contracts/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/metaflow-contracts)](https://pypi.org/project/metaflow-contracts/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Catch bad data between Metaflow steps before it silently corrupts your pipeline.

## The problem

Metaflow passes data between steps as untyped artifacts on `self`. When a step produces the wrong type — a string where downstream expects a float, a missing field, a None that slipped through — the failure surfaces steps later, far from the source. By then the error message is confusing and the run is already wasted. There is no built-in way to declare what a step promises to produce or requires to receive.

## Quick start

```bash
pip install metaflow-contracts
```

```python
from metaflow import FlowSpec, step
from metaflow_contracts import contract

class MyFlow(FlowSpec):

    @step
    @contract(outputs={"scores": list[float]})
    def start(self):
        self.scores = load_scores()
        self.next(self.classify)

    @step
    @contract(outputs={"label": str, "confidence": float})
    def classify(self):
        self.label, self.confidence = model.predict(self.scores)
        self.next(self.end)

    @step
    def end(self):
        print(self.label, self.confidence)
```

If `scores` is not a `list[float]` when `start` finishes, the run fails immediately with a clear message pointing at that step — not three steps later.

## Install

```bash
# Core (plain Python type hints)
pip install metaflow-contracts

# With Pydantic support
pip install "metaflow-contracts[pydantic]"

# With beartype for generic type checking (list[int], dict[str, float], etc.)
pip install "metaflow-contracts[beartype]"

# Everything
pip install "metaflow-contracts[pydantic,beartype]"
```

## Usage

### Validate outputs (primary pattern)

Validate what a step produces. Errors point at the step that caused them.

```python
@step
@contract(outputs={"label": str, "confidence": float})
def classify(self):
    self.label = model.predict(self.scores)   # ContractViolationError if wrong type
    self.confidence = model.score(self.scores)
    self.next(self.end)
```

### Validate with a Pydantic model

For steps with complex outputs or existing Pydantic schemas:

```python
from pydantic import BaseModel, field_validator

class ClassifyOutput(BaseModel):
    label: str
    confidence: float

    @field_validator("confidence")
    @classmethod
    def must_be_probability(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0 and 1")
        return v

@step
@contract(outputs=ClassifyOutput)
def classify(self):
    self.label = "cat"
    self.confidence = 1.5   # ContractViolationError: confidence must be between 0 and 1
    self.next(self.end)
```

### Validate inputs (defensive pattern)

Use `inputs=` when consuming artifacts from steps you don't own — third-party flows, shared libraries, or fan-in joins:

```python
@step
@contract(inputs={"raw_data": list[dict]}, outputs={"result": float})
def join(self):
    # inputs validated before body runs
    self.result = aggregate(self.raw_data)
    self.next(self.end)
```

## How it works

`@contract` wraps the step function. Input contracts run before the step body; output contracts run after. On failure a `ContractViolationError` is raised with the step name, phase (`input`/`output`), field name, expected type, and actual type.

Plain dict specs use `beartype` for generic type checking when available, falling back to `isinstance` for simple types. Pydantic specs delegate to `model_validate`. The two backends are protocol-compatible — you can mix them across steps.

## Development

```bash
git clone https://github.com/npow/metaflow-contracts
cd metaflow-contracts
pip install -e ".[dev]"
pytest          # 108 tests, 94%+ coverage
ruff check .    # lint
mypy metaflow_contracts  # type check
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
