from app.demo import demo_sources


def test_demo_mode_produces_daily_aggregates_without_individual_shipments() -> None:
    daily, searches, boxes, parties = demo_sources("Europe/Madrid")
    assert len(daily) == 31
    assert all(set(row) == {"date", "count", "total_weight"} for row in daily)
    assert all(row["count"] > 0 and row["total_weight"] > 0 for row in daily)
    assert searches and boxes and parties
