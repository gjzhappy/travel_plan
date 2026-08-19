from datetime import date,time
from travel_plan.validation.opening_hours import can_visit,hours_for_day

H={"weekly_hours":{"mon":None,"tue":["09:00","17:00"],"wed":["09:00","17:00"],"thu":["09:00","17:00"],"fri":["09:00","17:00"],"sat":["09:00","18:00"],"sun":["09:00","18:00"]},"special_dates":{"2026-10-01":["08:30","19:00"]},"latest_entry_time":"16:00"}
def test_weekday_weekend_closed():
    assert hours_for_day(H,date(2026,8,18))[1]==time(17)
    assert hours_for_day(H,date(2026,8,22))[1]==time(18)
    assert hours_for_day(H,date(2026,8,17)) is None
def test_special_overrides_and_latest_entry():
    assert hours_for_day(H,date(2026,10,1))==(time(8,30),time(19))
    assert can_visit(H,date(2026,10,1),time(15,30),60)
    assert not can_visit(H,date(2026,10,1),time(16,1),30)

