# SCM Evaluation Benchmark — Argentine Legal Corpus

Formal benchmark for evaluating the **Small Concept Model (SCM) v2** against human expert annotations on Argentine legal texts. This corpus supports the validation study described in:

> Lerer, I.A. (2026). *LLS SKaaS: Legal Skills as a Service — Interpretable Legal AI Infrastructure for the LATAM Mid-Market*. Zenodo. DOI: TBD upon publication.

## What this repository contains

| Path | Description |
|---|---|
| `protocol/annotation_guide.md` | Instructions for annotating attorneys |
| `protocol/principles_reference.md` | Reference card for the 24 Universal Legal Principles (Spanish) |
| `cases/cases_index.json` | Index of all 50 cases with metadata |
| `cases/ARG-*.json` | Individual case files (text + metadata) |
| `annotations/template.json` | Blank annotation template |
| `annotations/example_annotation.json` | Completed example |
| `scripts/evaluate.py` | Evaluation script (kappa, MAE, correlation) |
| `scripts/submit_scm.py` | Script to run SCM API on all cases |
| `scm_outputs/` | SCM v2 outputs (populated by submit_scm.py) |
| `results/` | Evaluation reports (populated by evaluate.py) |

## The 24 Universal Legal Principles

The SCM evaluates legal texts against these 24 principles of the Lerer Architecture:

| # | Principle | Branch |
|---|---|---|
| 1 | Legalidad | Public Law |
| 2 | Igualdad | Constitutional |
| 3 | Proporcionalidad | Administrative / Criminal |
| 4 | Razonabilidad | Constitutional |
| 5 | DebidoProceso | Procedural |
| 6 | DefensaEnJuicio | Procedural |
| 7 | PresuncionInocencia | Criminal |
| 8 | NonBisInIdem | Criminal |
| 9 | Irretroactividad | Civil / Criminal |
| 10 | BuenaFe | Civil / Commercial |
| 11 | AutonomiaVoluntad | Contract |
| 12 | PactaSuntServanda | Contract |
| 13 | RebusSicStantibus | Contract |
| 14 | EnriquecimientoSinCausa | Civil |
| 15 | Responsabilidad | Civil / Criminal |
| 16 | Causalidad | Civil / Criminal |
| 17 | Solidaridad | Labor / Social |
| 18 | Subsidiariedad | Administrative |
| 19 | CosaJuzgada | Procedural |
| 20 | SeguridadJuridica | Transversal |
| 21 | Congruencia | Procedural |
| 22 | MotivacionDelActo | Administrative |
| 23 | ControlJudicial | Constitutional |
| 24 | Transparencia | Administrative |

## Participating as an annotator

Open a GitHub Issue using the **Annotator Signup** template. Participation requires a valid Argentine bar association membership (matrícula de abogado). Each case receives at least two independent annotations; disagreements above 0.3 on any principle are arbitrated by a third annotator.

Annotators are credited in the acknowledgments of the validation paper.

## Running the evaluation

```bash
pip install -r requirements.txt

# 1. Run SCM on all cases (requires API access)
python scripts/submit_scm.py --endpoint https://your-lls-endpoint/v1/scm --token sk_live_...

# 2. After collecting human annotations, run evaluation
python scripts/evaluate.py

# Results saved to results/evaluation_report.json and results/evaluation_report.md
```

## Citation

If you use this benchmark, please cite:

```bibtex
@misc{lerer2026skaas,
  title  = {LLS SKaaS: Legal Skills as a Service — Interpretable Legal AI Infrastructure for the LATAM Mid-Market},
  author = {Lerer, Ignacio Adrián},
  year   = {2026},
  note   = {Zenodo preprint. DOI forthcoming.}
}
```

## License

CC-BY 4.0 — Ignacio Adrián Lerer / Lerer Legal Skills, Buenos Aires, Argentina.

Case texts are derived from public-domain Argentine judicial materials (SAIJ, CSJN). Original sources are cited in each case file.
