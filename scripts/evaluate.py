"""
evaluate.py — SCM Evaluation Benchmark
Computes inter-annotator agreement and SCM vs. human expert agreement.

Usage:
    python scripts/evaluate.py [--annotations_dir annotations/] [--scm_dir scm_outputs/]

Outputs:
    results/evaluation_report.json
    results/evaluation_report.md
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import cohen_kappa_score, confusion_matrix

PRINCIPLES = [
    "Legalidad", "Igualdad", "Proporcionalidad", "Razonabilidad",
    "DebidoProceso", "DefensaEnJuicio", "PresuncionInocencia", "NonBisInIdem",
    "Irretroactividad", "BuenaFe", "AutonomiaVoluntad", "PactaSuntServanda",
    "RebusSicStantibus", "EnriquecimientoSinCausa", "Responsabilidad",
    "Causalidad", "Solidaridad", "Subsidiariedad", "CosaJuzgada",
    "SeguridadJuridica", "Congruencia", "MotivacionDelActo",
    "ControlJudicial", "Transparencia",
]

HIGH_THRESHOLD = 0.5  # Score >= this → "high relevance" for binary kappa


def load_annotations(ann_dir: str) -> dict[str, list[dict]]:
    """Returns {case_id: [annotation_dict, ...]}"""
    by_case: dict[str, list[dict]] = defaultdict(list)
    ann_path = Path(ann_dir)
    for f in ann_path.glob("*.json"):
        if f.name in ("template.json", "example_annotation.json"):
            continue
        try:
            with open(f) as fh:
                ann = json.load(fh)
            case_id = ann.get("case_id")
            if case_id and ann.get("scores"):
                by_case[case_id].append(ann)
        except Exception as e:
            print(f"  Warning: could not load {f.name}: {e}", file=sys.stderr)
    return dict(by_case)


def load_scm_outputs(scm_dir: str) -> dict[str, dict]:
    """Returns {case_id: scm_output_dict}"""
    scm_path = Path(scm_dir)
    outputs = {}
    for f in scm_path.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            case_id = f.stem  # filename = case_id
            outputs[case_id] = data
        except Exception as e:
            print(f"  Warning: could not load SCM output {f.name}: {e}", file=sys.stderr)
    return outputs


def extract_score_vector(annotation: dict) -> dict[str, float]:
    """Extract principle scores from an annotation dict."""
    scores = annotation.get("scores", {})
    return {p: (scores.get(p) or {}).get("score") or 0.0 for p in PRINCIPLES}


def extract_scm_vector(scm_output: dict) -> dict[str, float]:
    """Extract principle scores from an SCM v2 output dict."""
    # SCM v2 uses 'scores' or 'details'
    if "scores" in scm_output:
        return {p: scm_output["scores"].get(p, 0.0) for p in PRINCIPLES}
    if "details" in scm_output:
        return {p: scm_output["details"].get(p, {}).get("score", 0.0) for p in PRINCIPLES}
    if "principles_scores" in scm_output:
        return {p: scm_output["principles_scores"].get(p, 0.0) for p in PRINCIPLES}
    return {p: 0.0 for p in PRINCIPLES}


def discretize(scores: list[float], threshold: float = HIGH_THRESHOLD) -> list[int]:
    return [1 if s >= threshold else 0 for s in scores]


def inter_annotator_kappa(ann_list: list[dict]) -> Optional[float]:
    """Compute weighted kappa between the first two annotations."""
    if len(ann_list) < 2:
        return None
    v1 = list(extract_score_vector(ann_list[0]).values())
    v2 = list(extract_score_vector(ann_list[1]).values())
    d1 = discretize(v1)
    d2 = discretize(v2)
    if len(set(d1)) < 2 and len(set(d2)) < 2:
        return 1.0 if d1 == d2 else 0.0
    try:
        return cohen_kappa_score(d1, d2, weights="linear")
    except Exception:
        return None


def mean_annotation(ann_list: list[dict]) -> dict[str, float]:
    """Compute mean score per principle across all annotations."""
    vectors = [extract_score_vector(a) for a in ann_list]
    return {p: float(np.mean([v[p] for v in vectors])) for p in PRINCIPLES}


def compute_mae(human: dict[str, float], scm: dict[str, float]) -> float:
    diffs = [abs(human[p] - scm[p]) for p in PRINCIPLES]
    return float(np.mean(diffs))


def compute_correlation(human: dict[str, float], scm: dict[str, float]) -> Optional[float]:
    h = [human[p] for p in PRINCIPLES]
    s = [scm[p] for p in PRINCIPLES]
    if np.std(h) == 0 or np.std(s) == 0:
        return None
    r, _ = pearsonr(h, s)
    return float(r)


def evaluate(annotations_dir: str, scm_dir: str) -> dict:
    print("Loading annotations...")
    annotations = load_annotations(annotations_dir)
    print(f"  {len(annotations)} cases with annotations")

    print("Loading SCM outputs...")
    scm_outputs = load_scm_outputs(scm_dir)
    print(f"  {len(scm_outputs)} cases with SCM outputs")

    # Cases with both human annotations and SCM outputs
    comparable = set(annotations.keys()) & set(scm_outputs.keys())
    print(f"  {len(comparable)} cases comparable (both human + SCM)")

    # Per-case results
    case_results = []
    all_human_scores = {p: [] for p in PRINCIPLES}
    all_scm_scores   = {p: [] for p in PRINCIPLES}
    kappas_iaa = []

    for case_id in sorted(comparable):
        ann_list = annotations[case_id]
        scm_vec  = extract_scm_vector(scm_outputs[case_id])
        human_mean = mean_annotation(ann_list)
        mae  = compute_mae(human_mean, scm_vec)
        corr = compute_correlation(human_mean, scm_vec)
        kappa_iaa = inter_annotator_kappa(ann_list)

        if kappa_iaa is not None:
            kappas_iaa.append(kappa_iaa)

        for p in PRINCIPLES:
            all_human_scores[p].append(human_mean[p])
            all_scm_scores[p].append(scm_vec[p])

        case_results.append({
            "case_id":       case_id,
            "n_annotators":  len(ann_list),
            "kappa_iaa":     round(kappa_iaa, 4) if kappa_iaa is not None else None,
            "mae_scm_human": round(mae, 4),
            "corr_scm_human": round(corr, 4) if corr is not None else None,
        })

    # Per-principle statistics
    principle_stats = []
    for p in PRINCIPLES:
        h = all_human_scores[p]
        s = all_scm_scores[p]
        if not h:
            continue
        mae_p = float(np.mean([abs(hi - si) for hi, si in zip(h, s)]))
        corr_p = None
        if np.std(h) > 0 and np.std(s) > 0:
            r, _ = pearsonr(h, s)
            corr_p = float(r)
        kappa_p = None
        dh = discretize(h)
        ds = discretize(s)
        if len(set(dh)) >= 2 or len(set(ds)) >= 2:
            try:
                kappa_p = float(cohen_kappa_score(dh, ds, weights="linear"))
            except Exception:
                pass
        principle_stats.append({
            "principle":    p,
            "mean_human":  round(float(np.mean(h)), 4),
            "mean_scm":    round(float(np.mean(s)), 4),
            "mae":         round(mae_p, 4),
            "correlation": round(corr_p, 4) if corr_p is not None else None,
            "kappa":       round(kappa_p, 4) if kappa_p is not None else None,
            "n_cases":     len(h),
        })

    # Overall binary kappa (SCM vs. mean human, all principles, all cases)
    flat_human = []
    flat_scm   = []
    for p in PRINCIPLES:
        flat_human.extend(discretize(all_human_scores[p]))
        flat_scm.extend(discretize(all_scm_scores[p]))

    overall_kappa = None
    if flat_human and len(set(flat_human)) >= 2:
        try:
            overall_kappa = float(cohen_kappa_score(flat_human, flat_scm, weights="linear"))
        except Exception:
            pass

    avg_mae  = float(np.mean([r["mae_scm_human"] for r in case_results])) if case_results else None
    avg_corr = float(np.mean([r["corr_scm_human"] for r in case_results if r["corr_scm_human"] is not None])) if case_results else None
    avg_iaa  = float(np.mean(kappas_iaa)) if kappas_iaa else None

    report = {
        "summary": {
            "n_cases_annotated":          len(annotations),
            "n_cases_with_scm":           len(scm_outputs),
            "n_cases_comparable":         len(comparable),
            "avg_annotators_per_case":    float(np.mean([len(v) for v in annotations.values()])) if annotations else 0,
            "avg_iaa_kappa":              round(avg_iaa, 4) if avg_iaa is not None else None,
            "avg_mae_scm_vs_human":       round(avg_mae, 4) if avg_mae is not None else None,
            "avg_corr_scm_vs_human":      round(avg_corr, 4) if avg_corr is not None else None,
            "overall_kappa_scm_vs_human": round(overall_kappa, 4) if overall_kappa is not None else None,
            "interpretation": _interpret(overall_kappa),
        },
        "per_case":      case_results,
        "per_principle": principle_stats,
    }

    return report


def _interpret(kappa: Optional[float]) -> str:
    if kappa is None:
        return "Insufficient data"
    if kappa >= 0.80: return "Almost perfect agreement"
    if kappa >= 0.60: return "Substantial agreement"
    if kappa >= 0.40: return "Moderate agreement"
    if kappa >= 0.20: return "Fair agreement"
    return "Slight agreement or less"


def generate_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# SCM Evaluation Benchmark — Results",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Cases annotated | {s['n_cases_annotated']} |",
        f"| Cases with SCM output | {s['n_cases_with_scm']} |",
        f"| Cases comparable | {s['n_cases_comparable']} |",
        f"| Avg annotators/case | {s['avg_annotators_per_case']:.1f} |",
        f"| Inter-annotator kappa (avg) | {s['avg_iaa_kappa']} |",
        f"| SCM vs human MAE (avg) | {s['avg_mae_scm_vs_human']} |",
        f"| SCM vs human correlation (avg) | {s['avg_corr_scm_vs_human']} |",
        f"| Overall kappa SCM vs human | {s['overall_kappa_scm_vs_human']} |",
        f"| Interpretation | {s['interpretation']} |",
        "",
        "## Per-Principle Results",
        "",
        "| Principle | Mean Human | Mean SCM | MAE | Correlation | Kappa |",
        "|---|---|---|---|---|---|",
    ]
    for p in report["per_principle"]:
        lines.append(
            f"| {p['principle']} | {p['mean_human']} | {p['mean_scm']} "
            f"| {p['mae']} | {p['correlation']} | {p['kappa']} |"
        )
    lines += ["", "## Per-Case Results", "",
              "| Case ID | Annotators | IAA Kappa | MAE (SCM vs human) | Correlation |",
              "|---|---|---|---|---|"]
    for c in report["per_case"]:
        lines.append(
            f"| {c['case_id']} | {c['n_annotators']} | {c['kappa_iaa']} "
            f"| {c['mae_scm_human']} | {c['corr_scm_human']} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SCM Evaluation Benchmark")
    parser.add_argument("--annotations_dir", default="annotations/")
    parser.add_argument("--scm_dir",         default="scm_outputs/")
    parser.add_argument("--output_dir",      default="results/")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    report = evaluate(args.annotations_dir, args.scm_dir)

    json_path = os.path.join(args.output_dir, "evaluation_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nJSON report saved to {json_path}")

    md_path = os.path.join(args.output_dir, "evaluation_report.md")
    with open(md_path, "w") as f:
        f.write(generate_markdown(report))
    print(f"Markdown report saved to {md_path}")

    s = report["summary"]
    print(f"\n{'='*50}")
    print(f"Overall kappa (SCM vs human): {s['overall_kappa_scm_vs_human']}")
    print(f"Interpretation: {s['interpretation']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
