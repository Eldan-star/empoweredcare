"""
Compute the measles risk index for each zone and store it (risk_scores).

    python scripts/run_risk.py                 # up to last month, 10 years of history
    python scripts/run_risk.py --end 2026-09 --years 8 --dry-run

Needs the OCHA boundaries (scripts/load_boundaries.py) and vaccination coverage
(scripts/load_immunization.py). Reported cases (indicator_counts) improve it but are not
required: without them, zones rank by susceptible build-up only.

Read docs/EVALUATION.md before using the index: on simulated data it ranks where measles
will be heaviest next quarter well, but it does not yet predict which quiet woredas will
ignite next.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from db.session import session_scope  # noqa: E402
from services.risk.panel import run  # noqa: E402
from services.risk.runner import build_panel, store  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compute and store the measles risk index.")
    today = date.today()
    last = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    ap.add_argument("--end", default=f"{last[0]}-{last[1]:02d}", help="last month, YYYY-MM")
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--level", type=int, default=2, help="2 = zones (default), 3 = woredas")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    end = tuple(int(x) for x in args.end.split("-"))

    with session_scope() as s:
        built = build_panel(s, end, args.years, args.level)
        for note in built.notes:
            print(note)
        if built.panel is None:
            return 1
        p = built.panel
        print(f"Zones scored: {len(p.pcodes)}; skipped (no coverage): {len(built.skipped_no_coverage)}")
        if built.births_estimated:
            print("Births: estimated from population x crude birth rate 31.9/1,000 where not loaded.")
        reported = int((~np.isnan(p.cases)).sum())
        print(f"Zone-months with reported cases: {reported} of {p.cases.size}")
        res = run(p)
        top = sorted(range(len(p.pcodes)), key=lambda j: -res.index[-1, j])[:10]
        print(f"Top 10 for {p.months[-1][0]}-{p.months[-1][1]:02d}: " + ", ".join(p.pcodes[j] for j in top))
        if args.dry_run:
            s.rollback()
            print("Dry run: nothing saved.")
        else:
            print(f"Saved {store(s, p, res)} risk scores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
