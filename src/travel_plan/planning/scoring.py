def route_score(
    priority: float,
    transport: int,
    waiting: int,
    tightness: int,
    repeated: int,
    spatial_discontinuity: int = 0,
    excess_transport: float = 0,
) -> float:
    """Return the deterministic, relative objective for one feasible POI route.

    Transport already prices every route leg.  ``spatial_discontinuity`` is more
    specific: it prices the avoidable excess of A -> B -> C over A -> C, which
    prevents a small relevance gain from causing an out-and-back ordering.  It is
    deliberately softer than ordinary transport and never affects feasibility.
    """
    return round(
        priority
        - transport * 0.7
        - waiting * 0.3
        - tightness * 1.2
        - repeated * 18
        - spatial_discontinuity * 0.45
        - excess_transport,
        2,
    )
