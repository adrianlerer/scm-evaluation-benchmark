"""
submit_scm.py — Submit all benchmark cases to the SCM API and save outputs.

Usage:
    python scripts/submit_scm.py \
        --endpoint https://your-lls-endpoint/v1/scm \
        --token sk_live_... \
        --cases_dir cases/ \
        --output_dir scm_outputs/

Rate: 1 request per second (configurable with --rate_limit_seconds).
"""

import json
import os
import time
import argparse
from pathlib import Path

import requests


def submit_case(endpoint: str, token: str, case: dict, timeout: int = 60) -> dict:
    payload = {
        "text":   case["text"],
        "source": case["id"],
    }
    headers = {
        "Content-Type": "application/json",
        "x-lerer-token": token,
        "x-skill-id": "lerer-contracts",
    }
    response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Submit benchmark cases to SCM API")
    parser.add_argument("--endpoint",            required=True,  help="SCM API endpoint URL")
    parser.add_argument("--token",               required=True,  help="License token (sk_live_...)")
    parser.add_argument("--cases_dir",           default="cases/")
    parser.add_argument("--output_dir",          default="scm_outputs/")
    parser.add_argument("--rate_limit_seconds",  type=float, default=1.0)
    parser.add_argument("--skip_existing",       action="store_true", help="Skip cases with existing output")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    cases_path  = Path(args.cases_dir)
    output_path = Path(args.output_dir)

    case_files = sorted(cases_path.glob("ARG-*.json"))
    print(f"Found {len(case_files)} case files")

    success = 0
    failed  = 0

    for case_file in case_files:
        case_id     = case_file.stem
        output_file = output_path / f"{case_id}.json"

        if args.skip_existing and output_file.exists():
            print(f"  Skipping {case_id} (output exists)")
            continue

        with open(case_file) as f:
            case = json.load(f)

        print(f"  Submitting {case_id}...", end=" ", flush=True)

        try:
            result = submit_case(args.endpoint, args.token, case)
            result["_case_id"]    = case_id
            result["_submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            with open(output_file, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print("OK")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1

        time.sleep(args.rate_limit_seconds)

    print(f"\nDone: {success} succeeded, {failed} failed")
    print(f"Outputs saved to {args.output_dir}")


if __name__ == "__main__":
    main()
