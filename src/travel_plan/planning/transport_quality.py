"""Deterministic daily transport burden measurements and policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportBurdenPolicy:
    preferred_total_min: int
    hard_total_min: int
    preferred_single_leg_min: int
    hard_single_leg_min: int


@dataclass(frozen=True)
class DailyTransportMetrics:
    total_transport_min: int
    largest_transfer_min: int
    average_transfer_min: float
    transport_leg_count: int
    long_transfer_count: int
    quality_status: str


def policy_for(config, pace: str) -> TransportBurdenPolicy:
    values = getattr(config, f"transport_{pace}", config.transport_moderate)
    return TransportBurdenPolicy(*values)


def transport_legs(day):
    """Return canonical incoming legs, once each, in itinerary order."""
    return [node for node in sorted(day.nodes, key=lambda n: n.start_time)
            if node.transport_mode and node.duration_min > 0]


def daily_transport_metrics(day, config, pace: str) -> DailyTransportMetrics:
    durations = [node.duration_min for node in transport_legs(day)]
    total = sum(durations)
    largest = max(durations, default=0)
    policy = policy_for(config, pace)
    if total > policy.hard_total_min or largest > policy.hard_single_leg_min:
        status = "excessive"
    elif total > policy.preferred_total_min or largest > policy.preferred_single_leg_min:
        status = "elevated"
    else:
        status = "good"
    return DailyTransportMetrics(
        total, largest, round(total / len(durations), 1) if durations else 0.0,
        len(durations), sum(value >= config.transport_long_transfer_min for value in durations), status,
    )


def excess_transport_penalty(total: int, largest: int, policy: TransportBurdenPolicy) -> float:
    """Softly price normal travel, then accelerate only beyond preferred limits."""
    total_excess = max(0, total - policy.preferred_total_min)
    leg_excess = max(0, largest - policy.preferred_single_leg_min)
    return total_excess * 0.8 + total_excess * total_excess / 100 + leg_excess * 0.9
