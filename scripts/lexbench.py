"""
lexbench.py — LexBench: SCM Evaluation Benchmark Suite
Extends evaluate.py with latency, consistency, and coverage metrics.

Inspired by the MLPerf evaluation methodology adapted for legal AI
(Reddi et al., 2022, "Introduction to Machine Learning Systems").

Metrics computed:
1. Human agreement (Cohen's kappa, MAE, correlation) — from evaluate.py
2. SCM latency per case (end-to-end API call time)
3. Triple-run consistency (confidence_spread distribution)
4. Principle activation coverage (how many principles score > 0 across corpus)
5. High-confidence precision (when confidence >= 0.8, how often does SCM agree with human?)

Usage:
    # Standard evaluation (requires human annotations + SCM outputs)
    python scripts/lexbench.py

    # Latency-only benchmark (no human annotations needed)
    python scripts/lexbench.py --latency_only \
        --endpoint https://your-endpoint/v1/scm \
        --token sk_live_...

    # Full LexBench suite
    python scripts/lexbench.py \
        --annotations_dir annotations/ \
        --scm_dir scm_outputs/ \
        --endpoint https://your-endpoint/v1/scm \
        --token sk_live_...

Outputs:
    results/lexbench_report.json
    results/lexbench_report.md
"""

import json
import os
import sys
import time
import argparse
import statistics
from pathlib import Path
from typing import Optional
from collections import defaultdict

import numpy as np
import requests

# Re-use core evaluation logic from evaluate.py
sys.path.insert(0, str(Path(__file__).parent))
from evaluate import (
    load_annotations, load_scm_outputs, extract_score_vector,
    extract_scm_vector, compute_mae, compute_correlation,
    inter_annotator_kappa, mean_annotation, PRINCIPLES, HIGH_THRESHOLD,
    discretize
)

try:
    from sklearn.metrics import cohen_kappa_score
except ImportError:
    print("Install scikit-learn: pip install scikit-learn", file=sys.stderr)
    sys.exit(1)


# ─── LexBench thresholds (inspired by Kimi/ML Systems book §12) ────────────

LATENCY_SLA = {
    "interactive":  1.0,   # < 1s  — Q&A, quick classification
    "analytical":   3.0,   # < 3s  — contract risk assessment
    "batch":        8.0,   # < 8s  — bulk summarization
}

HIGH_CONFIDENCE_THRESHOLD = 0.8   # confidence >= this → high-confidence prediction
CONSISTENCY_SPREAD_OK     = 0.15  # spread < this → stable (triple-run)
MIN_COVERAGE_PRINCIPLES   = 8     # at least this many principles should be activated
                                  # across the full 50-case corpus


# ─── Latency benchmark ──────────────────────────────────────────────────────

def benchmark_latency(
    cases_dir:  str,
    endpoint:   str,
    token:      str,
    n_cases:    int = 10,
    rate_limit: float = 1.0,
) -> dict:
    """
    Runs n_cases cases through the SCM API and measures latency.
    Returns per-case timings and SLA compliance rates.
    """
    cases_path = Path(cases_dir)
    case_files = sorted(cases_path.glob("ARG-*.json"))[:n_cases]

    timings = []
    failures = 0

    print(f"  Running latency benchmark on {len(case_files)} cases...")

    for f in case_files:
        with open(f) as fh:
            case = json.load(fh)

        headers = {
            "Content-Type": "application/json",
            "x-lerer-token": token,
        }
        payload = {"text": case["text"], "source": case["id"]}

        t0 = time.perf_counter()
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            elapsed = time.perf_counter() - t0
            timings.append({"case_id": case["id"], "latency_s": round(elapsed, 3)})
        except Exception as e:
            failures += 1
            print(f"    FAIL {case['id']}: {e}", file=sys.stderr)

        time.sleep(rate_limit)

    if not timings:
        return {"error": "No successful latency measurements"}

    lats = [t["latency_s"] for t in timings]

    return {
        "n_cases":          len(timings),
        "failures":         failures,
        "mean_latency_s":   round(statistics.mean(lats), 3),
        "p50_latency_s":    round(statistics.median(lats), 3),
        "p95_latency_s":    round(sorted(lats)[int(len(lats) * 0.95)], 3),
        "max_latency_s":    round(max(lats), 3),
        "sla_interactive":  round(sum(1 for l in lats if l < LATENCY_SLA["interactive"]) / len(lats), 3),
        "sla_analytical":   round(sum(1 for l in lats if l < LATENCY_SLA["analytical"]) / len(lats), 3),
        "sla_batch":        round(sum(1 for l in lats if l < LATENCY_SLA["batch"]) / len(lats), 3),
        "per_case":         timings,
    }


# ─── Consistency benchmark (triple-run spread) ──────────────────────────────

def benchmark_consistency(scm_outputs: dict) -> dict:
    """
    Analyzes confidence_spread values in SCM outputs.
    High spread = unstable; low spread = consistent.
    The SCM's triple-run consensus should produce spread < 0.15 for most principles.
    """
    all_spreads: dict[str, list[float]] = defaultdict(list)
    cases_with_spread = 0

    for case_id, output in scm_outputs.items():
        spread = output.get("confidence_spread")
        if not spread:
            continue
        cases_with_spread += 1
        for p in PRINCIPLES:
            val = spread.get(p)
            if val is not None:
                all_spreads[p].append(float(val))

    if not all_spreads:
        return {"note": "No confidence_spread data in SCM outputs. Run with SCM v2+ endpoint."}

    principle_consistency = []
    unstable_principles = []

    for p in PRINCIPLES:
        vals = all_spreads.get(p, [])
        if not vals:
            continue
        avg_spread = float(np.mean(vals))
        pct_stable = sum(1 for v in vals if v < CONSISTENCY_SPREAD_OK) / len(vals)
        principle_consistency.append({
            "principle":    p,
            "avg_spread":   round(avg_spread, 4),
            "pct_stable":   round(pct_stable, 3),
            "n_cases":      len(vals),
        })
        if avg_spread >= CONSISTENCY_SPREAD_OK:
            unstable_principles.append(p)

    overall_stable = float(np.mean([
        v for vals in all_spreads.values() for v in vals
        if v < CONSISTENCY_SPREAD_OK
    ])) if all_spreads else 0.0

    return {
        "cases_with_spread_data": cases_with_spread,
        "overall_pct_stable":     round(
            sum(1 for vals in all_spreads.values() for v in vals if v < CONSISTENCY_SPREAD_OK) /
            max(1, sum(len(v) for v in all_spreads.values())), 3
        ),
        "unstable_principles":    unstable_principles,
        "per_principle":          sorted(principle_consistency, key=lambda x: -x["avg_spread"]),
        "interpretation": (
            "HIGH CONSISTENCY — triple-run consensus is reliable"
            if len(unstable_principles) <= 3 else
            "MODERATE CONSISTENCY — review flagged principles"
            if len(unstable_principles) <= 8 else
            "LOW CONSISTENCY — consider increasing consensus runs or reviewing prompts"
        ),
    }


# ─── Coverage benchmark ─────────────────────────────────────────────────────

def benchmark_coverage(scm_outputs: dict, annotations: dict) -> dict:
    """
    Measures how many distinct principles are activated (score > 0.3)
    across the full corpus. A well-calibrated system should activate
    most principles in a diverse 50-case corpus.
    """
    scm_activated:   set[str] = set()
    human_activated: set[str] = set()

    for case_id, output in scm_outputs.items():
        vec = extract_scm_vector(output)
        for p, score in vec.items():
            if score >= 0.3:
                scm_activated.add(p)

    for case_id, ann_list in annotations.items():
        mean = mean_annotation(ann_list)
        for p, score in mean.items():
            if score >= 0.3:
                human_activated.add(p)

    never_activated_scm = [p for p in PRINCIPLES if p not in scm_activated]
    never_activated_human = [p for p in PRINCIPLES if p not in human_activated]

    return {
        "scm_principles_activated":         len(scm_activated),
        "human_principles_activated":       len(human_activated),
        "principles_never_activated_scm":   never_activated_scm,
        "principles_never_activated_human": never_activated_human,
        "coverage_adequate":                len(scm_activated) >= MIN_COVERAGE_PRINCIPLES,
        "note": (
            f"A diverse 50-case corpus should activate at least {MIN_COVERAGE_PRINCIPLES} "
            f"distinct principles at score >= 0.3."
        ),
    }


# ─── High-confidence precision ──────────────────────────────────────────────

def benchmark_high_confidence_precision(
    annotations: dict,
    scm_outputs: dict,
) -> dict:
    """
    When the SCM reports high confidence (>= 0.8), how often does it agree
    with human expert scores (within 0.2)?
    High-confidence predictions should be more reliable than average.
    """
    hc_agreements = []
    hc_total = 0

    comparable = set(annotations.keys()) & set(scm_outputs.keys())

    for case_id in comparable:
        output = scm_outputs[case_id]
        details = output.get("details", {})
        human_mean = mean_annotation(annotations[case_id])

        for p in PRINCIPLES:
            detail = details.get(p, {})
            confidence = detail.get("confidence", None)
            scm_score  = detail.get("score", None)

            if confidence is None or scm_score is None:
                continue
            if confidence < HIGH_CONFIDENCE_THRESHOLD:
                continue

            hc_total += 1
            human_score = human_mean.get(p, 0.0)
            agrees = abs(scm_score - human_score) <= 0.2
            hc_agreements.append(agrees)

    if not hc_agreements:
        return {
            "note": "No high-confidence predictions found in SCM outputs. "
                    "Check that outputs include 'details.confidence' fields (SCM v2)."
        }

    precision = sum(hc_agreements) / len(hc_agreements)

    return {
        "high_confidence_predictions": hc_total,
        "agreements_within_0_2":       sum(hc_agreements),
        "precision":                   round(precision, 4),
        "threshold_used":              HIGH_CONFIDENCE_THRESHOLD,
        "interpretation": (
            "HIGH-CONFIDENCE PREDICTIONS ARE RELIABLE (>= 90% agreement)"
            if precision >= 0.90 else
            "MODERATE RELIABILITY (80-90% agreement)"
            if precision >= 0.80 else
            "LOW RELIABILITY — high-confidence threshold may need calibration"
        ),
    }


# ─── Main LexBench runner ────────────────────────────────────────────────────

def run_lexbench(
    annotations_dir: str,
    scm_dir:         str,
    cases_dir:       str,
    output_dir:      str,
    endpoint:        Optional[str] = None,
    token:           Optional[str] = None,
    latency_only:    bool = False,
    n_latency_cases: int = 10,
) -> dict:

    os.makedirs(output_dir, exist_ok=True)
    report: dict = {"lexbench_version": "1.0", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    # ── Latency ──────────────────────────────────────────────────────────────
    if endpoint and token:
        print("Running latency benchmark...")
        report["latency"] = benchmark_latency(
            cases_dir, endpoint, token, n_cases=n_latency_cases
        )
    else:
        report["latency"] = {"note": "No endpoint provided. Skipped."}

    if latency_only:
        _save(report, output_dir)
        return report

    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading annotations and SCM outputs...")
    annotations = load_annotations(annotations_dir)
    scm_outputs = load_scm_outputs(scm_dir)
    print(f"  {len(annotations)} annotated cases, {len(scm_outputs)} SCM outputs")

    # ── Human agreement (from evaluate.py logic) ──────────────────────────────
    print("Computing human agreement metrics...")
    from evaluate import evaluate as run_evaluate
    report["human_agreement"] = run_evaluate(annotations_dir, scm_dir)["summary"]

    # ── Consistency ───────────────────────────────────────────────────────────
    print("Analyzing triple-run consistency...")
    report["consistency"] = benchmark_consistency(scm_outputs)

    # ── Coverage ──────────────────────────────────────────────────────────────
    print("Measuring principle activation coverage...")
    report["coverage"] = benchmark_coverage(scm_outputs, annotations)

    # ── High-confidence precision ─────────────────────────────────────────────
    print("Computing high-confidence precision...")
    report["high_confidence"] = benchmark_high_confidence_precision(annotations, scm_outputs)

    _save(report, output_dir)
    _print_summary(report)
    return report


def _save(report: dict, output_dir: str) -> None:
    json_path = os.path.join(output_dir, "lexbench_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nLexBench report saved to {json_path}")

    md_path = os.path.join(output_dir, "lexbench_report.md")
    with open(md_path, "w") as f:
        f.write(_to_markdown(report))
    print(f"Markdown report saved to {md_path}")


def _print_summary(report: dict) -> None:
    print("\n" + "=" * 60)
    print("  LexBench Summary")
    print("=" * 60)

    lat = report.get("latency", {})
    if "mean_latency_s" in lat:
        print(f"  Latency (mean):       {lat['mean_latency_s']}s")
        print(f"  SLA interactive (<1s): {lat['sla_interactive']*100:.0f}%")
        print(f"  SLA analytical  (<3s): {lat['sla_analytical']*100:.0f}%")

    ha = report.get("human_agreement", {})
    if ha:
        print(f"  Overall kappa:         {ha.get('overall_kappa_scm_vs_human')}")
        print(f"  Interpretation:        {ha.get('interpretation')}")

    cons = report.get("consistency", {})
    if "overall_pct_stable" in cons:
        print(f"  Triple-run stability:  {cons['overall_pct_stable']*100:.0f}%")
        print(f"  Interpretation:        {cons.get('interpretation')}")

    hc = report.get("high_confidence", {})
    if "precision" in hc:
        print(f"  High-conf precision:   {hc['precision']*100:.0f}%")

    print("=" * 60)


def _to_markdown(report: dict) -> str:
    lines = ["# LexBench Report", f"\nGenerated: {report.get('timestamp', 'N/A')}", ""]

    # Latency
    lat = report.get("latency", {})
    lines += ["## Latency", ""]
    if "mean_latency_s" in lat:
        lines += [
            "| Metric | Value |", "|---|---|",
            f"| Mean latency | {lat['mean_latency_s']}s |",
            f"| P50 | {lat['p50_latency_s']}s |",
            f"| P95 | {lat['p95_latency_s']}s |",
            f"| SLA interactive (<1s) | {lat['sla_interactive']*100:.0f}% |",
            f"| SLA analytical (<3s)  | {lat['sla_analytical']*100:.0f}% |",
            f"| SLA batch (<8s)       | {lat['sla_batch']*100:.0f}% |",
        ]
    else:
        lines.append(lat.get("note", "No data"))

    # Human agreement summary
    ha = report.get("human_agreement", {})
    if ha:
        lines += ["", "## Human Agreement", "",
                  "| Metric | Value |", "|---|---|",
                  f"| Cases comparable | {ha.get('n_cases_comparable')} |",
                  f"| Avg IAA kappa | {ha.get('avg_iaa_kappa')} |",
                  f"| SCM vs human MAE | {ha.get('avg_mae_scm_vs_human')} |",
                  f"| Overall kappa | {ha.get('overall_kappa_scm_vs_human')} |",
                  f"| **Interpretation** | **{ha.get('interpretation')}** |"]

    # Consistency
    cons = report.get("consistency", {})
    if "overall_pct_stable" in cons:
        lines += ["", "## Triple-Run Consistency", "",
                  f"- Overall stable predictions: **{cons['overall_pct_stable']*100:.0f}%**",
                  f"- Interpretation: **{cons.get('interpretation')}**"]
        if cons.get("unstable_principles"):
            lines.append(f"- Unstable principles: {', '.join(cons['unstable_principles'])}")

    # High-confidence
    hc = report.get("high_confidence", {})
    if "precision" in hc:
        lines += ["", "## High-Confidence Precision", "",
                  f"- High-confidence predictions: {hc['high_confidence_predictions']}",
                  f"- Agreement with human (within 0.2): **{hc['precision']*100:.0f}%**",
                  f"- Interpretation: **{hc.get('interpretation')}**"]

    # Coverage
    cov = report.get("coverage", {})
    if "scm_principles_activated" in cov:
        lines += ["", "## Principle Coverage", "",
                  f"- SCM activates: **{cov['scm_principles_activated']}/24** principles",
                  f"- Human activates: **{cov['human_principles_activated']}/24** principles"]
        if cov.get("principles_never_activated_scm"):
            lines.append(
                f"- Never activated by SCM: {', '.join(cov['principles_never_activated_scm'])}"
            )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LexBench — SCM Evaluation Suite")
    parser.add_argument("--annotations_dir", default="annotations/")
    parser.add_argument("--scm_dir",         default="scm_outputs/")
    parser.add_argument("--cases_dir",       default="cases/")
    parser.add_argument("--output_dir",      default="results/")
    parser.add_argument("--endpoint",        default=None, help="SCM API endpoint for latency test")
    parser.add_argument("--token",           default=None, help="License token sk_live_...")
    parser.add_argument("--latency_only",    action="store_true")
    parser.add_argument("--n_latency_cases", type=int, default=10)
    args = parser.parse_args()

    run_lexbench(
        annotations_dir = args.annotations_dir,
        scm_dir         = args.scm_dir,
        cases_dir       = args.cases_dir,
        output_dir      = args.output_dir,
        endpoint        = args.endpoint,
        token           = args.token,
        latency_only    = args.latency_only,
        n_latency_cases = args.n_latency_cases,
    )


if __name__ == "__main__":
    main()
