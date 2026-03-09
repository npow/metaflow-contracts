class ContractViolationError(Exception):
    """Raised when a step's artifacts do not satisfy a contract."""

    def __init__(self, step: str, phase: str, detail: str) -> None:
        super().__init__(f"ContractViolationError in step '{step}' [{phase}]: {detail}")
        self.step = step
        self.phase = phase
        self.detail = detail
