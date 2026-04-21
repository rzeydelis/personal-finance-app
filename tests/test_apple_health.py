from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from src.api.apple_health_parser import parse_apple_health_export


def _import_app_or_skip():
    try:
        import app  # type: ignore
        return app
    except Exception as exc:
        pytest.skip(f"Skipping: unable to import web app module: {exc}")


def _apple_dt(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")


def test_parse_apple_health_export_builds_summary():
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=1)
    recent_end = recent + timedelta(hours=1)
    sleep_start = recent.replace(hour=22, minute=0, second=0, microsecond=0)
    sleep_end = sleep_start + timedelta(hours=8)
    old = now - timedelta(days=40)
    old_end = old + timedelta(hours=1)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Apple Watch" unit="count" creationDate="{_apple_dt(recent)}" startDate="{_apple_dt(recent)}" endDate="{_apple_dt(recent_end)}" value="1200" />
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Apple Watch" unit="count" creationDate="{_apple_dt(recent)}" startDate="{_apple_dt(recent)}" endDate="{_apple_dt(recent_end)}" value="1800" />
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Apple Watch" unit="count" creationDate="{_apple_dt(old)}" startDate="{_apple_dt(old)}" endDate="{_apple_dt(old_end)}" value="9999" />
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch" value="HKCategoryValueSleepAnalysisAsleep" creationDate="{_apple_dt(sleep_start)}" startDate="{_apple_dt(sleep_start)}" endDate="{_apple_dt(sleep_end)}" />
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Apple Watch" unit="count/min" creationDate="{_apple_dt(recent)}" startDate="{_apple_dt(recent)}" endDate="{_apple_dt(recent_end)}" value="54" />
  <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Health" unit="lb" creationDate="{_apple_dt(recent)}" startDate="{_apple_dt(recent)}" endDate="{_apple_dt(recent_end)}" value="182.4" />
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="45" durationUnit="min" totalDistance="5.1" totalDistanceUnit="mi" totalEnergyBurned="410" totalEnergyBurnedUnit="kcal" sourceName="Apple Watch" creationDate="{_apple_dt(recent)}" startDate="{_apple_dt(recent)}" endDate="{_apple_dt(recent_end)}" />
</HealthData>
"""

    result = parse_apple_health_export(BytesIO(xml.encode("utf-8")), lookback_days=7)

    assert result["success"] is True
    summary = result["summary"]
    assert summary["metadata"]["records_processed"] == 5
    assert summary["workout_summary"]["total_workouts"] == 1
    assert summary["recent_summary"]["steps"]["total"] == 3000.0
    assert summary["recent_summary"]["sleep_hours"]["total"] == 8.0
    assert summary["recent_summary"]["resting_heart_rate"]["average"] == 54.0
    assert summary["recent_summary"]["body_mass"]["latest"] == 182.4
    assert summary["workout_summary"]["total_duration_minutes"] == 45.0
    assert summary["workout_summary"]["total_distance_miles"] == 5.1
    assert "steps" in summary["metadata"]["available_metrics"]
    assert all(day.get("steps", 0) != 9999 for day in summary["daily_metrics"])


def test_health_page_renders(add_web_to_syspath):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert b"Apple Health" in response.data
