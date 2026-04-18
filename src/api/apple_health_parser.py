import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, IO, Iterable, Optional, Tuple, Union

try:
    from defusedxml import ElementTree as ET
except Exception:
    import xml.etree.ElementTree as ET


APPLE_HEALTH_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%d %H:%M:%S",
)

QUANTITY_METRICS = {
    "HKQuantityTypeIdentifierStepCount": {
        "key": "steps",
        "label": "Steps",
        "aggregation": "sum",
        "unit": "steps",
    },
    "HKQuantityTypeIdentifierActiveEnergyBurned": {
        "key": "active_energy_burned",
        "label": "Active Energy Burned",
        "aggregation": "sum",
        "unit": "kcal",
    },
    "HKQuantityTypeIdentifierAppleExerciseTime": {
        "key": "exercise_minutes",
        "label": "Exercise Minutes",
        "aggregation": "sum",
        "unit": "min",
    },
    "HKQuantityTypeIdentifierDistanceWalkingRunning": {
        "key": "walking_running_distance",
        "label": "Walking + Running Distance",
        "aggregation": "sum",
        "unit": "mi",
    },
    "HKQuantityTypeIdentifierFlightsClimbed": {
        "key": "flights_climbed",
        "label": "Flights Climbed",
        "aggregation": "sum",
        "unit": "flights",
    },
    "HKQuantityTypeIdentifierHeartRate": {
        "key": "heart_rate",
        "label": "Heart Rate",
        "aggregation": "average",
        "unit": "bpm",
    },
    "HKQuantityTypeIdentifierRestingHeartRate": {
        "key": "resting_heart_rate",
        "label": "Resting Heart Rate",
        "aggregation": "average",
        "unit": "bpm",
    },
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": {
        "key": "heart_rate_variability",
        "label": "Heart Rate Variability",
        "aggregation": "average",
        "unit": "ms",
    },
    "HKQuantityTypeIdentifierBodyMass": {
        "key": "body_mass",
        "label": "Body Mass",
        "aggregation": "latest",
        "unit": "lb",
    },
    "HKQuantityTypeIdentifierBodyFatPercentage": {
        "key": "body_fat_percentage",
        "label": "Body Fat Percentage",
        "aggregation": "latest",
        "unit": "%",
    },
}

SLEEP_ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleep",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
}

SLEEP_IN_BED_VALUES = {
    "HKCategoryValueSleepAnalysisInBed",
}


def _parse_apple_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in APPLE_HEALTH_DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_number(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _normalize_metric_value(metric_key: str, value: float, unit: Optional[str]) -> float:
    unit_normalized = (unit or "").strip().lower()

    if metric_key == "walking_running_distance":
        if unit_normalized in {"km", "kilometer", "kilometers"}:
            return value * 0.621371
        if unit_normalized in {"m", "meter", "meters"}:
            return value * 0.000621371
    elif metric_key == "body_mass":
        if unit_normalized in {"kg", "kilogram", "kilograms"}:
            return value * 2.20462
    elif metric_key == "body_fat_percentage":
        if value <= 1:
            return value * 100
    elif metric_key == "active_energy_burned":
        if unit_normalized in {"kj", "kilojoule", "kilojoules"}:
            return value * 0.239006
    elif metric_key == "exercise_minutes":
        if unit_normalized in {"s", "sec", "secs", "second", "seconds"}:
            return value / 60.0
        if unit_normalized in {"h", "hr", "hrs", "hour", "hours"}:
            return value * 60.0

    return value


def _normalize_duration_minutes(value: Optional[float], unit: Optional[str]) -> float:
    if value is None:
        return 0.0
    unit_normalized = (unit or "").strip().lower()
    if unit_normalized in {"hour", "hours", "hr", "hrs", "h"}:
        return value * 60.0
    if unit_normalized in {"second", "seconds", "sec", "secs", "s"}:
        return value / 60.0
    return value


def _clean_workout_type(raw_type: Optional[str]) -> str:
    if not raw_type:
        return "Other"
    cleaned = raw_type.replace("HKWorkoutActivityType", "")
    chars = []
    for index, char in enumerate(cleaned):
        if index and char.isupper() and cleaned[index - 1].islower():
            chars.append(" ")
        chars.append(char)
    return "".join(chars).strip() or "Other"


def _series_summary(points: Dict[str, float], aggregation: str, unit: str) -> Dict[str, Any]:
    if not points:
        return {}

    ordered_dates = sorted(points.keys())
    values = [points[date] for date in ordered_dates]
    span_days = max(1, (datetime.fromisoformat(ordered_dates[-1]) - datetime.fromisoformat(ordered_dates[0])).days + 1)

    recent_values = values[-7:]
    prior_values = values[-14:-7]

    recent_average = sum(recent_values) / len(recent_values)
    prior_average = (sum(prior_values) / len(prior_values)) if prior_values else None
    trend_percent = None
    if prior_average not in (None, 0):
        trend_percent = ((recent_average - prior_average) / abs(prior_average)) * 100.0

    summary = {
        "unit": unit,
        "days_with_data": len(values),
        "date_range": {
            "start": ordered_dates[0],
            "end": ordered_dates[-1],
            "days_covered": span_days,
        },
        "latest": _round_number(values[-1]),
        "minimum": _round_number(min(values)),
        "maximum": _round_number(max(values)),
        "recent_average": _round_number(recent_average),
        "trend_percent": _round_number(trend_percent),
    }

    if aggregation == "sum":
        total = sum(values)
        summary["total"] = _round_number(total)
        summary["average_daily"] = _round_number(total / span_days)
    else:
        summary["average"] = _round_number(sum(values) / len(values))

    if prior_average is not None:
        summary["prior_average"] = _round_number(prior_average)

    return summary


def _latest_value_summary(points: Dict[str, float], unit: str) -> Dict[str, Any]:
    if not points:
        return {}

    ordered_dates = sorted(points.keys())
    latest_date = ordered_dates[-1]
    latest_value = points[latest_date]
    previous_value = points[ordered_dates[-2]] if len(ordered_dates) > 1 else None

    change = None
    change_percent = None
    if previous_value not in (None, 0):
        change = latest_value - previous_value
        change_percent = (change / abs(previous_value)) * 100.0
    elif previous_value is not None:
        change = latest_value - previous_value

    return {
        "unit": unit,
        "latest": _round_number(latest_value),
        "latest_date": latest_date,
        "previous": _round_number(previous_value),
        "change": _round_number(change),
        "change_percent": _round_number(change_percent),
        "days_with_data": len(points),
    }


def _build_daily_metrics(metric_points: Dict[str, Dict[str, float]], max_days: int = 120) -> Iterable[Dict[str, Any]]:
    all_dates = sorted({date for points in metric_points.values() for date in points.keys()})
    if len(all_dates) > max_days:
        all_dates = all_dates[-max_days:]

    rows = []
    for date in all_dates:
        row = {"date": date}
        has_metric = False
        for metric_key, points in metric_points.items():
            if date in points:
                row[metric_key] = _round_number(points[date])
                has_metric = True
        if has_metric:
            rows.append(row)
    return rows


def _open_source(source: Union[str, Path, IO[bytes]]) -> Tuple[IO[bytes], bool]:
    if hasattr(source, "read"):
        file_obj = source  # type: ignore[assignment]
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return file_obj, False
    path = Path(source)
    return path.open("rb"), True


def parse_apple_health_export(source: Union[str, Path, IO[bytes]], lookback_days: int = 90) -> Dict[str, Any]:
    lookback_days = max(1, min(int(lookback_days or 90), 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    metric_points: Dict[str, Dict[str, float]] = defaultdict(dict)
    metric_buckets: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    record_counts = Counter()
    source_counts = Counter()
    workout_type_counts = Counter()
    recent_workouts = []
    available_metrics = set()
    total_workout_minutes = 0.0
    total_workout_distance = 0.0
    total_workout_energy = 0.0

    records_processed = 0
    workouts_processed = 0
    first_date = None
    last_date = None

    file_obj, should_close = _open_source(source)

    try:
        for _, elem in ET.iterparse(file_obj, events=("end",)):
            if elem.tag == "Record":
                record_type = elem.attrib.get("type")
                start_dt = _parse_apple_datetime(elem.attrib.get("startDate"))
                end_dt = _parse_apple_datetime(elem.attrib.get("endDate")) or start_dt

                if end_dt is None or end_dt < cutoff:
                    elem.clear()
                    continue

                day_key = end_dt.date().isoformat()
                source_name = elem.attrib.get("sourceName")
                if source_name:
                    source_counts[source_name] += 1

                first_date = min(first_date, day_key) if first_date else day_key
                last_date = max(last_date, day_key) if last_date else day_key

                if record_type in QUANTITY_METRICS:
                    spec = QUANTITY_METRICS[record_type]
                    raw_value = _safe_float(elem.attrib.get("value"))
                    if raw_value is None:
                        elem.clear()
                        continue

                    metric_key = spec["key"]
                    normalized_value = _normalize_metric_value(metric_key, raw_value, elem.attrib.get("unit"))
                    aggregation = spec["aggregation"]

                    if aggregation == "sum":
                        current = metric_points[metric_key].get(day_key, 0.0)
                        metric_points[metric_key][day_key] = current + normalized_value
                    else:
                        metric_buckets[metric_key][day_key].append(normalized_value)

                    record_counts[metric_key] += 1
                    available_metrics.add(metric_key)
                    records_processed += 1
                elif record_type == "HKCategoryTypeIdentifierSleepAnalysis" and start_dt:
                    duration_hours = max((end_dt - start_dt).total_seconds(), 0.0) / 3600.0
                    sleep_value = elem.attrib.get("value")

                    if sleep_value in SLEEP_ASLEEP_VALUES:
                        current = metric_points["sleep_hours"].get(day_key, 0.0)
                        metric_points["sleep_hours"][day_key] = current + duration_hours
                        record_counts["sleep_hours"] += 1
                        available_metrics.add("sleep_hours")
                        records_processed += 1
                    elif sleep_value in SLEEP_IN_BED_VALUES:
                        current = metric_points["time_in_bed_hours"].get(day_key, 0.0)
                        metric_points["time_in_bed_hours"][day_key] = current + duration_hours
                        record_counts["time_in_bed_hours"] += 1
                        available_metrics.add("time_in_bed_hours")
                        records_processed += 1

                elem.clear()
            elif elem.tag == "Workout":
                start_dt = _parse_apple_datetime(elem.attrib.get("startDate"))
                end_dt = _parse_apple_datetime(elem.attrib.get("endDate")) or start_dt
                if end_dt is None or end_dt < cutoff:
                    elem.clear()
                    continue

                workout_type = _clean_workout_type(elem.attrib.get("workoutActivityType"))
                duration_minutes = _normalize_duration_minutes(
                    _safe_float(elem.attrib.get("duration")),
                    elem.attrib.get("durationUnit"),
                )
                distance_miles = _safe_float(elem.attrib.get("totalDistance"))
                if distance_miles is not None:
                    distance_miles = _normalize_metric_value(
                        "walking_running_distance",
                        distance_miles,
                        elem.attrib.get("totalDistanceUnit"),
                    )
                energy_kcal = _safe_float(elem.attrib.get("totalEnergyBurned"))
                if energy_kcal is not None:
                    energy_kcal = _normalize_metric_value(
                        "active_energy_burned",
                        energy_kcal,
                        elem.attrib.get("totalEnergyBurnedUnit"),
                    )

                day_key = end_dt.date().isoformat()
                workout_type_counts[workout_type] += 1
                workouts_processed += 1

                first_date = min(first_date, day_key) if first_date else day_key
                last_date = max(last_date, day_key) if last_date else day_key

                recent_workouts.append(
                    {
                        "date": day_key,
                        "type": workout_type,
                        "duration_minutes": _round_number(duration_minutes),
                        "distance_miles": _round_number(distance_miles),
                        "energy_kcal": _round_number(energy_kcal),
                    }
                )
                total_workout_minutes += duration_minutes or 0.0
                total_workout_distance += distance_miles or 0.0
                total_workout_energy += energy_kcal or 0.0

                elem.clear()
    except ET.ParseError as exc:
        return {
            "success": False,
            "summary": {},
            "error": f"Invalid Apple Health XML: {exc}",
        }
    finally:
        if should_close:
            file_obj.close()

    for record_type, spec in QUANTITY_METRICS.items():
        metric_key = spec["key"]
        aggregation = spec["aggregation"]
        if aggregation in {"average", "latest"} and metric_key in metric_buckets:
            for day_key, values in metric_buckets[metric_key].items():
                if not values:
                    continue
                metric_points[metric_key][day_key] = sum(values) / len(values)

    if not records_processed and not workouts_processed:
        return {
            "success": False,
            "summary": {},
            "error": "No supported Apple Health records were found in the selected date range.",
        }

    recent_workouts = sorted(recent_workouts, key=lambda item: item["date"], reverse=True)[:15]

    recent_summary = {
        "steps": _series_summary(metric_points.get("steps", {}), "sum", "steps"),
        "sleep_hours": _series_summary(metric_points.get("sleep_hours", {}), "sum", "hours"),
        "time_in_bed_hours": _series_summary(metric_points.get("time_in_bed_hours", {}), "sum", "hours"),
        "active_energy_burned": _series_summary(metric_points.get("active_energy_burned", {}), "sum", "kcal"),
        "exercise_minutes": _series_summary(metric_points.get("exercise_minutes", {}), "sum", "min"),
        "walking_running_distance": _series_summary(metric_points.get("walking_running_distance", {}), "sum", "mi"),
        "flights_climbed": _series_summary(metric_points.get("flights_climbed", {}), "sum", "flights"),
        "heart_rate": _series_summary(metric_points.get("heart_rate", {}), "average", "bpm"),
        "resting_heart_rate": _series_summary(metric_points.get("resting_heart_rate", {}), "average", "bpm"),
        "heart_rate_variability": _series_summary(metric_points.get("heart_rate_variability", {}), "average", "ms"),
        "body_mass": _latest_value_summary(metric_points.get("body_mass", {}), "lb"),
        "body_fat_percentage": _latest_value_summary(metric_points.get("body_fat_percentage", {}), "%"),
    }

    recent_summary = {key: value for key, value in recent_summary.items() if value}

    summary = {
        "lookback_days": lookback_days,
        "date_range": {
            "start": first_date,
            "end": last_date,
        },
        "metadata": {
            "records_processed": records_processed,
            "workouts_processed": workouts_processed,
            "available_metrics": sorted(available_metrics),
            "top_sources": [
                {"name": name, "record_count": count}
                for name, count in source_counts.most_common(5)
            ],
        },
        "record_counts": dict(record_counts),
        "recent_summary": recent_summary,
        "workout_summary": {
            "total_workouts": workouts_processed,
            "total_duration_minutes": _round_number(total_workout_minutes),
            "total_distance_miles": _round_number(total_workout_distance),
            "total_energy_kcal": _round_number(total_workout_energy),
            "top_workout_types": [
                {"type": workout_type, "count": count}
                for workout_type, count in workout_type_counts.most_common(5)
            ],
            "recent_workouts": recent_workouts,
        },
        "daily_metrics": list(_build_daily_metrics(metric_points)),
    }

    return {
        "success": True,
        "summary": summary,
        "error": None,
    }


def parse_apple_health_file_to_json(input_path: Union[str, Path], output_path: Union[str, Path], lookback_days: int = 90) -> Dict[str, Any]:
    result = parse_apple_health_export(input_path, lookback_days=lookback_days)
    if not result.get("success"):
        return result

    output = Path(output_path)
    output.write_text(json.dumps(result["summary"], indent=2), encoding="utf-8")
    return result
