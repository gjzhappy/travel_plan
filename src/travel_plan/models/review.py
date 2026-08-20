from dataclasses import asdict, dataclass, field

@dataclass
class ReviewIssue:
    scope: str; type: str; message: str; day: int | None = None

@dataclass
class ReviewResult:
    passed: bool; issues: list[ReviewIssue] = field(default_factory=list); repair_instructions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return the schema-shaped message passed back to the intent agent."""
        return asdict(self)
