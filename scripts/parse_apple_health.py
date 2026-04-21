import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.apple_health_parser import parse_apple_health_export


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Apple Health export.xml into compact JSON for downstream analysis."
    )
    parser.add_argument("input_xml", help="Path to Apple Health export.xml")
    parser.add_argument(
        "-d",
        "--lookback-days",
        type=int,
        default=90,
        help="Only include the most recent N days of data (default: 90).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional path to write the parsed JSON summary. Defaults to stdout.",
    )
    args = parser.parse_args()

    result = parse_apple_health_export(args.input_xml, lookback_days=args.lookback_days)
    if not result.get("success"):
        print(result.get("error", "Apple Health parsing failed."), file=sys.stderr)
        return 1

    payload = json.dumps(result["summary"], indent=2)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
