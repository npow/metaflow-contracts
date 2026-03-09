# metaflow-contracts

[![CI](https://github.com/npow/metaflow-contracts/actions/workflows/ci.yml/badge.svg)](https://github.com/npow/metaflow-contracts/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/metaflow-contracts)](https://pypi.org/project/metaflow-contracts/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Catch bad data between Metaflow steps before it corrupts your pipeline.

## The problem

Metaflow passes data between steps as untyped artifacts on `self`. A step produces the wrong type — a string where downstream expects a float, a `None` that slipped through — and the failure surfaces two steps later with a confusing traceback pointing nowhere near the cause. There's no built-in way for a step to declare what it promises to produce.

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

If `scores` is the wrong type when `start` finishes, the run fails immediately at that step — not somewhere downstream:

```
ContractViolationError in step 'start' [output]: 'scores' expected list, got str
```

## Install

```bash
# Core — plain Python type hints
pip install metaflow-contracts

# With Pydantic support
pip install "metaflow-contracts[pydantic]"

# With beartype for generic types (list[int], dict[str, float], Optional, Union…)
pip install "metaflow-contracts[beartype]"

# Everything
pip install "metaflow-contracts[pydantic,beartype]"
```

## Usage

### Output contracts (primary pattern)

Put the contract on the step that produces the data. Errors point at the source.

```python
@step
@contract(outputs={"label": str, "confidence": float})
def classify(self):
    self.label = model.predict(self.scores)
    self.confidence = model.score(self.scores)
    self.next(self.end)
```

```
# Wrong type:   ContractViolationError in step 'classify' [output]: 'confidence' expected float, got str
# Missing field: ContractViolationError in step 'classify' [output]: 'label' is missing (expected str)
```

### Pydantic models

Use a Pydantic model when you want field-level validators or already have schemas defined elsewhere.

```python
from pydantic import BaseModel, field_validator

class ClassifyOutput(BaseModel):
    label: str
    confidence: float

    @field_validator("confidence")
    @classmethod
    def must_be_probability(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0 and 1")
        return v

@step
@contract(outputs=ClassifyOutput)
def classify(self):
    self.label = "cat"
    self.confidence = 1.5  # raises: confidence must be between 0 and 1
    self.next(self.end)
```

### Input contracts (defensive pattern)

Use `inputs=` when consuming artifacts from steps you don't own — third-party flows or fan-in joins where you can't add an output contract upstream.

```python
@step
@contract(inputs={"raw_data": list[dict]}, outputs={"result": float})
def join(self):
    self.result = aggregate(self.raw_data)
    self.next(self.end)
```

## How it works

`@contract` wraps the step. Input contracts run before the body; output contracts run after. On failure, `ContractViolationError` is raised with the step name, phase (`input`/`output`), field, expected type, and actual type.

Plain dict specs use `beartype` for generic checking when available, falling back to `isinstance` for simple types. Pydantic specs delegate to `model_validate`. Both backends are interchangeable — you can mix them freely across steps.

## Development

```bash
git clone git@github.com:npow/metaflow-contracts.git
cd metaflow-contracts
pip install -e ".[dev]"
pytest                   # 108 tests, 94%+ coverage
ruff check .             # lint
mypy metaflow_contracts  # type check
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
