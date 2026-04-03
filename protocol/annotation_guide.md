# SCM Evaluation — Annotation Protocol

**Version:** 1.0 — April 2026  
**Estimated time per case:** 10–20 minutes  
**Total cases:** 50 (each annotator receives a randomized subset of 25)

---

## Before you begin

Read `principles_reference.md` carefully. You will annotate each case against the 24 Universal Legal Principles of the Lerer Architecture. The goal is to record what a competent Argentine attorney would identify as the legally relevant principles in each text — based solely on what the text says, not on what you know about the case from other sources.

This is not a legal opinion. You are not advising a client. You are annotating a research corpus.

---

## The annotation task

For each case, you receive a short text (2–5 sentences) describing a legal situation. You assign two numbers to each of the 24 principles:

### Score (0.0 to 1.0)

| Value | Meaning |
|---|---|
| 0.0 | The principle is not engaged by this text |
| 0.3 | The principle is tangentially related but not a central issue |
| 0.7 | The principle is clearly applicable and legally relevant |
| 1.0 | The principle is the central axis of the legal situation described |

Intermediate values (0.1, 0.2, 0.4, 0.5, 0.6, 0.8, 0.9) are permitted but discouraged. The four anchor points above cover the vast majority of cases. Use intermediate values only when you have a specific reason.

### Confidence (0.0 to 1.0)

| Value | Meaning |
|---|---|
| 0.0 | You are uncertain whether this principle applies; the text is ambiguous |
| 0.5 | Moderate certainty; you would not be surprised if another attorney disagreed |
| 1.0 | Unambiguous from the text; another competent attorney would assign the same score |

Confidence is independent of score. A principle can have score = 0.0 and confidence = 1.0 (you are certain it does not apply) or score = 0.7 and confidence = 0.3 (you think it applies but the text is ambiguous).

---

## Rules

**Rule 1 — Text only.** Score based exclusively on what is stated in the case text. Do not use your knowledge of the real case, the parties, or the outcome. If the text does not mention something, it does not score.

**Rule 2 — Do not inflate.** In most legal situations, two or three principles are central and the rest are irrelevant. A typical annotation will have 2–4 principles above 0.5 and the majority at 0.0. If you are assigning high scores to more than six principles, reconsider.

**Rule 3 — Do not discuss.** Do not discuss your annotations with other annotators until the study is complete. Inter-rater disagreement is a data point; do not contaminate it.

**Rule 4 — Time yourself.** Record the time you spend on each case in the `time_spent_minutes` field. This informs the study's cost estimates.

**Rule 5 — Note ambiguities.** Use the `notes` field in each principle to flag anything that made the annotation difficult. These notes are used for arbitration and for improving the protocol.

---

## Inter-rater agreement and arbitration

Each case receives annotations from at least two attorneys. Disagreements are measured per principle:

- **Agreement zone** (|score_A − score_B| ≤ 0.2): no arbitration needed; the mean is used
- **Review zone** (0.2 < |score_A − score_B| ≤ 0.3): flagged for discussion in the study report
- **Arbitration zone** (|score_A − score_B| > 0.3): a third annotator provides an independent score; the median of the three is used

The inter-rater reliability metric reported in the paper is weighted Cohen's kappa (κ), computed per principle and overall.

---

## How to submit

1. Copy `annotations/template.json` and rename it to `annotations/<ANNOTATOR_ID>_ARG-XXX.json`
2. Fill in all fields (no nulls when you submit)
3. Submit via the GitHub repository (pull request to `annotations/` directory) or by email to adrian@lerer.com.ar

Do not modify the case files or the template structure.

---

## Ethical obligations

You are a licensed attorney participating in academic research. Your annotations will be published (anonymized by annotator ID, not name) as part of an academic paper. By submitting annotations, you confirm that:

- You hold a valid Argentine bar association membership (matrícula)
- Your annotations represent your independent professional judgment
- You have not discussed your annotations with other study participants
- You consent to the anonymized publication of your annotations under CC-BY 4.0
