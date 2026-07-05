"""Eval harness — scores the pipeline's fit-score ranking against human labels.

Runs the real pipeline (SeedDatasetSource, offline, zero credentials) and compares the
ranking it produces to the include/exclude labels in labels.glow-lab.json:

  - precision@k for k in (3, 5, 7): of the top-k ranked KOLs, how many are labeled include
  - recall@7: of all labeled-include KOLs, how many appear in the top 7
  - the WORST disagreement ("wrong case"): the labeled-exclude KOL the ranking placed
    highest, or the labeled-include KOL it placed lowest — whichever is further out of
    place. When the ranking separates the classes perfectly, the wrong case degrades to
    the thinnest margin at the include/exclude boundary, because with n=11 provisional
    labels a clean separation is a smoke test, not a victory.

Usage (from backend/):
  ./.venv/Scripts/python.exe eval/run_eval.py    # Windows
  .venv/bin/python eval/run_eval.py              # macOS / Linux

Writes eval/results.json and prints a human-readable report. Directional harness, not a
benchmark — see eval/rubric.md for the honest framing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Script lives in backend/eval/; make backend/ importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to a legacy codepage; the report contains UTF-8 (Thai handles,
# dashes). Force UTF-8 so the text survives Git Bash / redirection intact.
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline import build_shortlist  # noqa: E402
from app.schemas import Kol  # noqa: E402
from app.sources.seed import SeedDatasetSource  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
LABELS_PATH = EVAL_DIR / "labels.glow-lab.json"
RESULTS_PATH = EVAL_DIR / "results.json"
PRECISION_KS = (3, 5, 7)
RECALL_K = 7


def load_labels(path: Path) -> tuple[dict[str, bool], dict[str, str], str]:
    """Return (id -> include, id -> reason, labeled_by) from the labels file."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    include = {row["id"]: bool(row["include"]) for row in spec["labels"]}
    reasons = {row["id"]: row["reason"] for row in spec["labels"]}
    return include, reasons, spec.get("labeled_by", "unknown")


def precision_at_k(ranked_ids: list[str], include: dict[str, bool], k: int) -> float:
    """Fraction of the top-k ranked KOLs that are labeled include."""
    top = ranked_ids[:k]
    return round(sum(1 for i in top if include[i]) / len(top), 3)


def recall_at_k(ranked_ids: list[str], include: dict[str, bool], k: int) -> float:
    """Fraction of all labeled-include KOLs that appear in the top k."""
    wanted = {i for i, inc in include.items() if inc}
    if not wanted:
        return 0.0
    return round(len(wanted & set(ranked_ids[:k])) / len(wanted), 3)


def worst_disagreement(
    ranked: list[Kol], include: dict[str, bool], reasons: dict[str, str]
) -> dict:
    """Identify the single worst label/ranking disagreement.

    Severity of an excluded KOL = how many labeled-include KOLs rank BELOW it (each is a
    real inversion: the ranking preferred a should-exclude over a should-include).
    Severity of an included KOL = how many labeled-exclude KOLs rank ABOVE it. The wrong
    case is the KOL with the highest severity; ties break toward the excluded side
    (recommending a bad KOL costs the client more than missing a good one).

    If severity is 0 everywhere (perfect separation), fall back to the boundary margin:
    the best-ranked exclude vs the worst-ranked include, reported honestly as "no
    inversion — this is the closest call, and where an independent rater would most
    plausibly flip a label."
    """
    ranked_ids = [k.id for k in ranked]
    by_id = {k.id: k for k in ranked}
    rank_of = {kid: i + 1 for i, kid in enumerate(ranked_ids)}

    excl_ranked = [kid for kid in ranked_ids if not include[kid]]
    incl_ranked = [kid for kid in ranked_ids if include[kid]]

    top_exclude = excl_ranked[0]  # best-ranked labeled-exclude
    bottom_include = incl_ranked[-1]  # worst-ranked labeled-include

    excl_severity = sum(1 for kid in incl_ranked if rank_of[kid] > rank_of[top_exclude])
    incl_severity = sum(1 for kid in excl_ranked if rank_of[kid] < rank_of[bottom_include])

    if excl_severity == 0 and incl_severity == 0:
        kind = "boundary_margin"
        subject = top_exclude
        margin = by_id[bottom_include].fit_score - by_id[top_exclude].fit_score
        explanation = (
            f"No inversion: every labeled-include KOL outranks every labeled-exclude KOL, so the "
            f"'wrong case' degrades to the thinnest margin at the boundary. {top_exclude} "
            f"({by_id[top_exclude].handle}) is labeled exclude yet scores fit "
            f"{by_id[top_exclude].fit_score}/100 at rank {rank_of[top_exclude]} — only {margin} points "
            f"below the last include, {bottom_include} ({by_id[bottom_include].handle}, fit "
            f"{by_id[bottom_include].fit_score}). The disagreement is structural: the label excludes "
            f"{top_exclude} on the conflict gate and a medium boost signal, but fit_score is a soft "
            f"ranking over topic/authenticity/recency and deliberately ignores the conflict gate "
            f"(gates route to human review; they are not ranking penalties). The score answers 'how "
            f"good a fit, fraud-adjusted' while the label answers 'would we hand this to the brand "
            f"today' — two different questions that happen to agree on ordering here. This is also "
            f"where an independent rater would most plausibly flip a label."
        )
    elif excl_severity >= incl_severity:
        kind = "excluded_ranked_high"
        subject = top_exclude
        explanation = (
            f"{top_exclude} ({by_id[top_exclude].handle}) is labeled exclude but ranks "
            f"{rank_of[top_exclude]} (fit {by_id[top_exclude].fit_score}), above {excl_severity} "
            f"labeled-include KOL(s)."
        )
    else:
        kind = "included_ranked_low"
        subject = bottom_include
        explanation = (
            f"{bottom_include} ({by_id[bottom_include].handle}) is labeled include but ranks "
            f"{rank_of[bottom_include]} (fit {by_id[bottom_include].fit_score}), below {incl_severity} "
            f"labeled-exclude KOL(s)."
        )

    k = by_id[subject]
    return {
        "kind": kind,
        "id": subject,
        "handle": k.handle,
        "rank": rank_of[subject],
        "fit_score": k.fit_score,
        "risk_level": k.risk.level,
        "risk_signals": [s.label for s in k.risk.signals],
        "conflict": k.conflict.status,
        "label_include": include[subject],
        "label_reason": reasons[subject],
        "explanation": explanation,
    }


def main() -> None:
    include, reasons, labeled_by = load_labels(LABELS_PATH)

    response = build_shortlist(SeedDatasetSource())
    ranked = response.kols  # already sorted by fit_score desc (ties keep fixture order)
    ranked_ids = [k.id for k in ranked]

    missing = set(ranked_ids) - set(include)
    extra = set(include) - set(ranked_ids)
    if missing or extra:
        raise SystemExit(f"Label/ranking mismatch — missing labels: {sorted(missing)}, "
                         f"labels without candidates: {sorted(extra)}")

    precision = {f"precision@{k}": precision_at_k(ranked_ids, include, k) for k in PRECISION_KS}
    recall = {f"recall@{RECALL_K}": recall_at_k(ranked_ids, include, RECALL_K)}
    wrong = worst_disagreement(ranked, include, reasons)

    results = {
        "brand": "glow-lab",
        "labeled_by": labeled_by,
        "n_candidates": len(ranked_ids),
        "n_labeled_include": sum(include.values()),
        "ranking": [
            {"rank": i + 1, "id": k.id, "handle": k.handle, "fit_score": k.fit_score,
             "risk_level": k.risk.level, "label_include": include[k.id]}
            for i, k in enumerate(ranked)
        ],
        "metrics": {**precision, **recall},
        "wrong_case": wrong,
        "caveats": [
            "Directional harness, not a benchmark: 11 KOLs, one brief, provisional solo labels.",
            "Labels were auto-drafted from the same curated fixture story the seed data encodes, "
            "so high agreement is partly by construction.",
            "To be re-run on the live seed pull (2 brands x 20 KOLs) with independently drawn labels.",
        ],
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")

    # ── human-readable report ──────────────────────────────────────────────
    print("Kollab eval — glow-lab fixtures vs provisional labels")
    print(f"labels: {labeled_by}")
    print()
    print(f"{'rank':>4}  {'id':<4} {'handle':<24} {'fit':>4}  {'risk':<7} label")
    for row in results["ranking"]:
        label = "include" if row["label_include"] else "EXCLUDE"
        print(f"{row['rank']:>4}  {row['id']:<4} {row['handle']:<24} {row['fit_score']:>4}"
              f"  {row['risk_level']:<7} {label}")
    print()
    for name, value in results["metrics"].items():
        print(f"  {name:<13} {value}")
    print()
    print(f"wrong case ({wrong['kind']}): {wrong['id']} {wrong['handle']} — "
          f"rank {wrong['rank']}, fit {wrong['fit_score']}, risk {wrong['risk_level']}")
    print(f"  {wrong['explanation']}")
    print()
    for c in results["caveats"]:
        print(f"  caveat: {c}")
    print()
    print(f"results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
