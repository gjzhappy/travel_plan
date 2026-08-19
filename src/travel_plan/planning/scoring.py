def route_score(priority: float, transport: int, waiting: int, tightness: int, repeated: int) -> float:
    return round(priority - transport*0.7 - waiting*0.3 - tightness*1.2 - repeated*18, 2)

