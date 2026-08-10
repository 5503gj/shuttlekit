import pytest

from shuttle_speed.realtime import RealtimeSpeedSession, SpeedSessionStore


def test_realtime_speed_from_two_points():
    session = RealtimeSpeedSession("venue-a", "court-01", fps=60, px_per_meter=50)
    session.add_point(0, 0, timestamp=0)
    state = session.add_point(50, 0, timestamp=1 / 60)
    assert state["current_speed_kmh"] == 216.0
    assert state["peak_speed_kmh"] == 216.0
    assert state["sample_count"] == 1


def test_calibration_updates_scale():
    session = RealtimeSpeedSession("venue-a", "court-01")
    assert session.calibrate(1340, 13.4) == pytest.approx(100)


def test_timestamp_must_increase():
    session = RealtimeSpeedSession("venue-a", "court-01")
    session.add_point(0, 0, timestamp=1)
    with pytest.raises(ValueError, match="timestamp"):
        session.add_point(1, 1, timestamp=1)


def test_venue_overview_contains_each_court():
    store = SpeedSessionStore()
    first = store.create("venue-a", "court-01")
    second = store.create("venue-a", "court-02")
    store.create("venue-b", "court-01")
    overview = store.overview("venue-a")
    assert {item["court_id"] for item in overview} == {first.court_id, second.court_id}
