class TravelError(Exception):
    """Base user-facing planner error."""


class RequirementError(TravelError):
    """Requirement JSON or parsed values violate the contract."""
class DataUnavailableError(TravelError):
    """An authoritative repository cannot supply required data."""
class MapError(TravelError):
    """A required map route failed."""
class NoFeasibleRouteError(TravelError):
    """No route satisfies the hard constraints."""
class ValidationError(TravelError):
    """A plan remains invalid after safe repair."""
class ReviewError(TravelError):
    """Review output is malformed."""
