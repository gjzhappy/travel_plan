from dataclasses import dataclass, field

@dataclass
class ReviewIssue:
    scope: str; type: str; message: str; day: int | None = None

@dataclass
class ReviewResult:
    passed: bool; issues: list[ReviewIssue] = field(default_factory=list); repair_instructions: list[str] = field(default_factory=list)
