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
class MustVisitResolutionError(TravelError):
    """A hard place expression cannot be resolved to one canonical POI."""
class ValidationError(TravelError):
    """A plan remains invalid after safe repair."""
class ReviewError(TravelError):
    """Review output is malformed."""
class AgentOutputValidationError(TravelError):
    """A named agent returned JSON that does not satisfy its boundary schema."""
class AmbiguousTargetNodeError(TravelError):
    """A NODE modification did not identify exactly one node."""
class LockedPlanConflict(TravelError):
    """A requested modification conflicts with a locked day."""
