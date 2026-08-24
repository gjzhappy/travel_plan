"""Single deterministic source of truth for attraction-density review."""


def max_attractions_for(requirement) -> int | None:
    limits = []
    if requirement.pace == "relaxed":
        limits.append(3)
    if requirement.party.child:
        limits.append(4)
    return min(limits) if limits else None
