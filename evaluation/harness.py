"""
Evaluation harness (SYSTEM_SPEC section 10, METHODOLOGY section 5).

Simulates Ethiopian measles with IDM's laser-measles, passes it through a PHEM-like
reporting layer, and scores:
- detection: do EPHI's thresholds, applied week by week to the data visible at the time,
  catch true outbreaks, how fast, and how many alerts are false?
- risk ranking: does the monthly risk index put next quarter's outbreaks in its top 10%
  more often than simple baselines?
- reconstruction: how close are the estimated reporting rates and susceptible pools to
  the simulator's truth?

Run (in the simulation environment, see requirements-sim.txt):
    python -m evaluation.harness                  # synthetic woredas, default scenarios
    python -m evaluation.harness --units db       # real OCHA woredas from the database
    python -m evaluation.harness --quick          # small run for a smoke test

Writes evaluation/reports/<date>-<name>.md and .json.
"""

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

from services.detection import diseases
from services.risk import measles_risk as mr
from services.risk.panel import Panel, run as run_panel
from simulation import ethiopia as eth

REPORTS = Path(__file__).resolve().parent / "reports"
HUB_DIR: Optional[Path] = None  # set by --hub: write Hubverse-layout model output (large)
MEASLES = diseases.get("measles")


@dataclass
class Scenario:
    name: str
    mixing: str = "gravity"
    seed: int = 1
    rate_mean: float = 0.12
    importation_rate: float = 0.05
    beta_scale: float = 1.0
    years: int = 15
    burn_in_years: int = 4
    note: str = ""


DEFAULT_SCENARIOS = [
    Scenario("gravity", "gravity", note="Simulator mixing is gravity (laser defaults); our model uses its own gravity exponents"),
    Scenario("radiation", "radiation", note="Mis-specified: simulator uses radiation mixing"),
    Scenario("stouffer", "stouffer", note="Mis-specified: simulator uses intervening-opportunities mixing"),
    Scenario("low-reporting", "gravity", seed=2, rate_mean=0.05, note="Only ~5% of infections reported"),
    Scenario("episodic", "gravity", seed=3, beta_scale=0.8,
             note="Lower transmission: more woredas between outbreaks, closer to Ethiopia's reported pattern"),
]


# --- Detection ---------------------------------------------------------------------------

def levels_as_of(rep: eth.Reported, t: int) -> tuple[np.ndarray, np.ndarray]:
    """EPHI levels for week t using only data visible at the end of week t. Vectorised
    form of services.detection.thresholds.evaluate (tests check they agree)."""
    s, c = rep.as_of(t)
    w = MEASLES.action.window_weeks
    s_win = np.nansum(s[max(0, t - w + 1):t + 1], axis=0)
    c_win = np.nansum(c[max(0, t - w + 1):t + 1], axis=0)
    action = (s_win >= MEASLES.action.suspected) | (c_win >= MEASLES.action.confirmed)
    alert = np.nan_to_num(s[t]) >= MEASLES.alert.suspected
    return action, alert


def episodes(flags: np.ndarray, gap: int = 4) -> list[tuple[int, int]]:
    """(week, unit) where a unit enters a level after `gap` weeks without it."""
    out = []
    W, U = flags.shape
    for u in range(U):
        last = -10 ** 6
        for t in np.flatnonzero(flags[:, u]):
            if t - last > gap:
                out.append((int(t), u))
            last = t
    return out


def score_detection(starts: list[tuple[int, int]], onsets: list[tuple[int, int]], t0: int, units: int,
                    weeks: int, transmitting: np.ndarray, before: int = 4, after: int = 8) -> dict:
    """Sensitivity and delay are scored against outbreak onsets. PPV counts an episode as
    real when true transmission was under way at its start (4-week true infections at or
    above the outbreak level), so alerts in units with continuous transmission are not
    called false just because those units never had a quiet period."""
    by_unit: dict[int, list[int]] = {}
    for t, u in starts:
        by_unit.setdefault(u, []).append(t)
    delays, detected = [], 0
    for t, u in onsets:
        hits = [s for s in by_unit.get(u, []) if t - before <= s <= t + after]
        if hits:
            detected += 1
            delays.append(min(hits, key=lambda s: abs(s - t)) - t)
    matched = sum(bool(transmitting[s, u]) for s, u in starts)
    unit_years = units * weeks / 52.0
    return {
        "outbreaks": len(onsets),
        "sensitivity": detected / len(onsets) if onsets else None,
        "ppv": matched / len(starts) if starts else None,
        "episodes": len(starts),
        "false_episodes_per_unit_year": (len(starts) - matched) / unit_years if unit_years else None,
        "detected": detected,
        "median_delay_days": float(np.median(delays) * 7) if delays else None,
        "share_detected_before_onset": float(np.mean(np.array(delays) <= 0)) if delays else None,
    }


# --- Risk ranking ------------------------------------------------------------------------

def monthly(truth: eth.Truth, rep: eth.Reported) -> tuple[list[tuple[int, int]], np.ndarray, np.ndarray, np.ndarray]:
    """Months covered by whole weeks (by each week's Monday), the week->month map, and
    monthly reported cases two ways: settled (every report that eventually arrived) and
    provisional (only what had arrived by the month's end). The risk panel uses
    provisional values for recent months and settled values for older ones."""
    W, U = truth.weekly_infections.shape
    month_of = []
    keys: list[tuple[int, int]] = []
    for w in range(W):
        d = truth.start + timedelta(weeks=w)
        k = (d.year, d.month)
        if not keys or keys[-1] != k:
            keys.append(k)
        month_of.append(len(keys) - 1)
    month_of = np.array(month_of)

    def agg(block):
        seen = ~np.isnan(block)
        return np.where(seen.any(axis=0), np.nansum(block, axis=0), np.nan)

    settled = np.full((len(keys), U), np.nan)
    provisional = np.full((len(keys), U), np.nan)
    for m in range(len(keys)):
        wk = np.flatnonzero(month_of == m)
        settled[m] = agg(rep.suspected[wk])
        s, _ = rep.as_of(int(wk[-1]))
        provisional[m] = agg(s[wk])
    return keys, month_of, settled, provisional


LARGE_PER_100K = 100.0   # outbreak "large": >=100 true infections per 100,000 in 12 weeks
TOP_BURDEN_SHARE = 0.10  # "high burden": the top 10% of units by true incidence next quarter
QUIET_MONTHS = 2         # ignition is ranked among units with no reported case for this long


def precision_recall_at_k(scores: np.ndarray, target: np.ndarray, k: int) -> tuple[float, float]:
    top = np.argsort(-scores, kind="mergesort")[:k]
    hits = target[top].sum()
    return hits / k, (hits / target.sum() if target.sum() else np.nan)


def rank_targets(candidates: dict, target: np.ndarray, m0: int, k_share: float,
                 eligible: Optional[np.ndarray] = None) -> dict:
    """Mean precision@k and recall@k over months m0.. for each candidate ranking, with k
    a share of the eligible units. candidates: name -> (months, units) scores; target and
    eligible: (months, units) bool."""
    T = target.shape[0]
    eligible = np.ones_like(target, bool) if eligible is None else eligible
    prec = {key: [] for key in candidates}
    rec = {key: [] for key in candidates}
    rates, ks = [], []
    for m in range(m0, T):
        idx = np.flatnonzero(eligible[m])
        if len(idx) < 10 or not target[m, idx].any():
            continue
        k = max(1, int(round(k_share * len(idx))))
        ks.append(k), rates.append(target[m, idx].mean())
        for key, sc in candidates.items():
            p, r = precision_recall_at_k(np.asarray(sc[m], float)[idx], target[m, idx], k)
            prec[key].append(p), rec[key].append(r)
    return {"months_scored": len(rates), "median_k": float(np.median(ks)) if ks else None,
            "base_rate": float(np.mean(rates)) if rates else None,
            "precision_at_k": {key: float(np.mean(v)) if v else None for key, v in prec.items()},
            "recall_at_k": {key: float(np.nanmean(v)) if v else None for key, v in rec.items()}}


def score_risk(res, panel: Panel, onset_months: list[tuple[int, int]], monthly_truth: np.ndarray,
               true_s_share: np.ndarray, m0: int, k_share: float = 0.1, seed: int = 0,
               extra: Optional[dict] = None) -> dict:
    """Two questions, matching how the index would be used:
    - high burden: which units will carry the most measles next quarter (top 10% by true
      incidence)? Scored over all units.
    - ignition: which currently quiet units (no reported case for QUIET_MONTHS months, as
      known at the time) will have a new outbreak next quarter? Scored among quiet units,
      since a unit already in transmission cannot have a new onset."""
    T, U = res.index.shape
    m_end = T - 3
    pop = panel.population
    nxt = np.zeros((T, U))
    for m in range(T - 3):
        nxt[m] = monthly_truth[m + 1:m + 4].sum(axis=0) / pop * 1e5
    cutoff = np.quantile(nxt, 1 - TOP_BURDEN_SHARE, axis=1, keepdims=True)
    high_burden = nxt >= cutoff
    near_burden = nxt >= np.quantile(nxt, 1 - 2 * TOP_BURDEN_SHARE, axis=1, keepdims=True)
    onset_next = np.zeros((T, U), bool)
    for m, u in onset_months:
        onset_next[max(0, m - 3):m, u] = True
    known = np.nan_to_num(panel.cases)
    prov = np.nan_to_num(panel.cases_provisional) if panel.cases_provisional is not None else known

    def as_known(m):  # settled history, provisional for the latest two months
        k = known[max(0, m - 11):m + 1].copy()
        k[-2:] = prov[max(0, m - 1):m + 1][-len(k[-2:]):]
        return k
    quiet = np.array([as_known(m)[-QUIET_MONTHS:].sum(axis=0) == 0 for m in range(T)])
    rng = np.random.default_rng(seed)
    last12 = np.array([as_known(m).sum(axis=0) for m in range(T)])
    candidates = {
        "index": res.lam, "index_3m": res.index_3m,
        "susceptible_share": res.s / pop,                    # ablation: our S only
        "low_mcv1": 1 - panel.mcv1, "last_12m_cases": last12, "random": rng.random((T, U)),
        "oracle_true_susceptibles": true_s_share,            # reference: simulator's true S
        **(extra or {}),
    }
    cut = lambda a: a[:m_end]
    cands = {n: cut(v) for n, v in candidates.items()}
    out = {"k_share": k_share,
           "high_burden_next_quarter": rank_targets(cands, cut(high_burden), m0, k_share),
           "near_miss_top20_next_quarter": rank_targets(cands, cut(near_burden), m0, k_share),
           "ignition_next_quarter": rank_targets(cands, cut(onset_next), m0, k_share, eligible=cut(quiet))}
    lead1, lead3 = [], []
    for m, u in onset_months:
        if m - 3 < m0:
            continue
        for lag, acc in ((1, lead1), (3, lead3)):
            pool = np.flatnonzero(quiet[m - lag])
            if u not in pool or len(pool) < 10:
                continue
            k = max(1, int(round(k_share * len(pool))))
            acc.append(u in pool[np.argsort(-res.lam[m - lag][pool])[:k]])
    out["ignitions_in_top_k_1_month_before"] = float(np.mean(lead1)) if lead1 else None
    out["ignitions_in_top_k_3_months_before"] = float(np.mean(lead3)) if lead3 else None
    return out


def spearman(a, b) -> float:
    ra, rb = mr.rank_index(a), mr.rank_index(b)
    return float(np.corrcoef(ra, rb)[0, 1])


# --- Scenario run ------------------------------------------------------------------------

def run_scenario(units: eth.Units, sc: Scenario) -> dict:
    truth = eth.simulate(units, years=sc.years, mixing=sc.mixing, seed=sc.seed,
                         importation_rate=sc.importation_rate, beta_scale=sc.beta_scale)
    rep = eth.report(truth, seed=sc.seed + 1, rate_mean=sc.rate_mean)
    W, U = truth.weekly_infections.shape
    t0 = sc.burn_in_years * 52
    all_onsets = [o for o in eth.outbreak_onsets(truth, units.population) if o[0] >= t0]
    onsets = [(t, u) for t, u, _ in all_onsets]
    large = [(t, u) for t, u, size in all_onsets if size >= LARGE_PER_100K]

    action = np.zeros((W, U), bool)
    alert = np.zeros((W, U), bool)
    for t in range(t0, W):
        action[t], alert[t] = levels_as_of(rep, t)
    inf = truth.weekly_infections.astype(float)
    roll = np.array([inf[max(0, t - 3):t + 1].sum(axis=0) for t in range(W)])
    transmitting = roll / units.population[None, :] * 1e5 >= 20.0
    ep_action = [e for e in episodes(action) if e[0] >= t0]
    ep_alert = [e for e in episodes(alert) if e[0] >= t0]
    detection = {
        "action_all": score_detection(ep_action, onsets, t0, U, W - t0, transmitting),
        "action_large": score_detection(ep_action, large, t0, U, W - t0, transmitting),
        "alert_all": score_detection(ep_alert, onsets, t0, U, W - t0, transmitting),
        "alert_large": score_detection(ep_alert, large, t0, U, W - t0, transmitting),
    }

    keys, month_of, cases, provisional = monthly(truth, rep)
    T = len(keys)
    births = np.tile(units.population * eth.CRUDE_BIRTH_RATE / 1000 / 12, (T, 1))
    panel = Panel(pcodes=units.pcodes, population=units.population.astype(float), lat=units.lat, lon=units.lon,
                  months=keys, births=births, mcv1=np.tile(units.mcv1, (T, 1)), mcv2=np.tile(units.mcv2, (T, 1)),
                  cases=cases, cases_provisional=provisional, region=units.region)
    res = run_panel(panel)
    m0 = int(month_of[t0])
    onset_months = [(int(month_of[t]), u) for t, u in onsets]
    monthly_truth = np.zeros((T, U))
    np.add.at(monthly_truth, month_of, truth.weekly_infections)
    month_end_tick = [min(int(np.flatnonzero(month_of == m)[-1]) // 2, truth.biweekly_susceptibles.shape[0] - 1)
                      for m in range(T)]
    true_s_share = truth.biweekly_susceptibles[month_end_tick] / units.population
    from evaluation import challengers
    extra = challengers.rankings(panel, res, m0, monthly_truth, true_s_share, seed=sc.seed)
    risk = score_risk(res, panel, onset_months, monthly_truth, true_s_share, m0, seed=sc.seed, extra=extra)
    if HUB_DIR is not None:
        import csv
        HUB_DIR.mkdir(parents=True, exist_ok=True)
        rows = challengers.hubverse_rows({"risk_index": res.lam, **extra}, panel, m0, sc.name)
        with open(HUB_DIR / f"{sc.name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(), w.writerows(rows)

    final_rho = res.rho[-1]
    est = res.rho_estimated[-1]
    true_s = truth.biweekly_susceptibles[-1] / units.population
    recon = {
        "rho_estimated_units": int(est.sum()),
        "rho_median_abs_error": float(np.median(np.abs(final_rho[est] - rep.reporting_rate[est]))) if est.any() else None,
        "rho_rank_correlation": spearman(final_rho[est], rep.reporting_rate[est]) if est.sum() > 2 else None,
        "susceptible_share_rank_correlation": spearman(res.s[-1] / units.population, true_s),
        "true_reporting_rate_median": float(np.median(rep.reporting_rate)),
    }
    return {"scenario": asdict(sc), "units": U, "weeks_scored": W - t0, "outbreaks": len(onsets),
            "large_outbreaks": len(large), "detection": detection, "risk": risk, "reconstruction": recon}


# --- Report ------------------------------------------------------------------------------

CANDIDATE_LABELS = [
    ("index", "**Risk index (1 month)**"), ("index_3m", "Risk index (3-month horizon)"),
    ("susceptible_share", "Our susceptible share alone (ablation)"),
    ("boosted_trees", "Challenger: gradient-boosted trees"),
    ("hybrid_regression", "**Hybrid: count regression + risk-model covariates**"),
    ("count_regression", "Challenger: endemic-epidemic count regression (hhh4-type)"),
    ("ar1_log", "Challenger: ARIMA(1,0,0) on log counts"),
    ("ewma", "Challenger: EWMA of reported incidence"),
    ("persistence", "Challenger: reported incidence, last 3 months"),
    ("low_mcv1", "Baseline: lowest MCV1"), ("last_12m_cases", "Baseline: most cases last 12 months"),
    ("random", "Baseline: random"),
    ("oracle_true_susceptibles", "_Reference: simulator's true susceptibles_"),
    ("oracle_recent_truth", "_Reference: true recent infections (perfect nowcast)_"),
    ("oracle_mechanistic", "_Reference: risk formula with true inputs (its ceiling)_"),
]


def _f(v, pct=False, nd=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{100 * v:.0f}%" if pct else f"{v:.{nd}f}"


def markdown(results: list[dict], units: eth.Units, name: str) -> str:
    L = [f"# Evaluation report: {name}", "",
         f"_Generated {date.today().isoformat()} by `evaluation/harness.py`._", "",
         "## What was run", "",
         f"- **Units:** {len(units.pcodes)} {'synthetic woreda-scale units (seeded, illustrative)' if units.synthetic else 'OCHA units from the database'}"
         f"; median population {int(np.median(units.population)):,}.",
         "- **Simulator:** IDM laser-measles biweekly SIR, split into weeks; Ethiopia crude birth rate 31.9/1,000.",
         "- **Reporting layer:** per-unit reporting rates, 0-4 week delays, ~10% missing weeks, ~15% backfilled 4-12 weeks late.",
         "- **True outbreak onset:** 4-week true infections reach 20 per 100,000 after 8+ weeks below 5 per 100,000. "
         f"**Large** outbreaks reach {LARGE_PER_100K:g} true infections per 100,000 within 12 weeks of onset.",
         "- **Detection:** EPHI measles thresholds applied each week to the data visible that week. A detection is a new episode within 4 weeks before to 8 weeks after onset. PPV: share of episodes starting while true transmission was under way (4-week true infections >= 20 per 100,000).",
         "- **Risk ranking:** each month, the top 10% of units by each ranking, scored against two targets: the units with the highest true incidence next quarter, and (among units reporting no cases) the units where a new outbreak starts next quarter. "
         "The simulator's true susceptible pool is shown as a reference: the best a ranking on susceptibility alone could do.",
         "", "## Results", ""]
    for r in results:
        sc, det, rk, rc = r["scenario"], r["detection"], r["risk"], r["reconstruction"]
        L += [f"### {sc['name']}", "", f"_{sc['note']}_ · mixing `{sc['mixing']}`, mean reporting rate {sc['rate_mean']:.0%}, "
              f"{r['weeks_scored']} weeks scored, {r['outbreaks']} true outbreaks ({r['large_outbreaks']} large).", "",
              "| Detection | Outbreaks | Sensitivity | PPV | False episodes / unit-year | Median delay (days) | Detected by onset |",
              "|---|---|---|---|---|---|---|"]
        for key, label in [("action_all", "Action threshold, all outbreaks"), ("action_large", "Action threshold, large outbreaks"),
                           ("alert_all", "Alert threshold, all outbreaks"), ("alert_large", "Alert threshold, large outbreaks")]:
            d = det[key]
            L.append(f"| {label} | {d['outbreaks']} | {_f(d['sensitivity'], True)} | {_f(d['ppv'], True)} | "
                     f"{_f(d['false_episodes_per_unit_year'])} | {_f(d['median_delay_days'], nd=0)} | {_f(d['share_detected_before_onset'], True)} |")
        for tkey, tlabel in [("high_burden_next_quarter", "the 10% of units with the highest true incidence next quarter (all units)"),
                             ("near_miss_top20_next_quarter", "the top 20% by true incidence next quarter (near misses count)"),
                             ("ignition_next_quarter", f"a new outbreak next quarter, among units with no reported case in the last {QUIET_MONTHS} months")]:
            t = rk[tkey]
            L += ["", f"**Risk ranking: top 10% vs {tlabel}** (base rate {_f(t['base_rate'], True)}, {t['months_scored']} months, median k {_f(t['median_k'], nd=0)})", "",
                  "| Ranking | Precision@k | Recall@k |", "|---|---|---|"]
            for key, label in CANDIDATE_LABELS:
                if key in t["precision_at_k"]:
                    L.append(f"| {label} | {_f(t['precision_at_k'][key], True)} | {_f(t['recall_at_k'][key], True)} |")
        L += ["", f"Ignitions whose unit was in the top 10% of quiet units one month before: {_f(rk['ignitions_in_top_k_1_month_before'], True)}; "
              f"three months before: {_f(rk['ignitions_in_top_k_3_months_before'], True)}.", "",
              f"Reconstruction: reporting rate estimated for {rc['rho_estimated_units']} units, median absolute error "
              f"{_f(rc['rho_median_abs_error'], nd=3)} (true median {_f(rc['true_reporting_rate_median'], nd=3)}), rank correlation "
              f"{_f(rc['rho_rank_correlation'])}; susceptible-share rank correlation with truth {_f(rc['susceptible_share_rank_correlation'])}.", ""]
    L += ["## How to read this", "",
          "- **The risk index is shown as a risk ranking only where it beats every baseline** (METHODOLOGY 4.6). Where it does not, it stays internal.",
          "- **Circularity:** the gravity scenario shares the gravity idea with our model, so its scores are optimistic; the radiation and stouffer scenarios test robustness to a different spread mechanism.",
          "- **Synthetic data cannot validate the model for Ethiopia.** It tests that the code and methods behave sensibly. Real validation needs EPHI bulletins and DHIS2 history.",
          ""]
    return "\n".join(L)


def main(argv: Optional[list[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--units", choices=["synthetic", "db"], default="synthetic")
    ap.add_argument("--n", type=int, default=400, help="number of synthetic units")
    ap.add_argument("--quick", action="store_true", help="small, fast run (smoke test)")
    ap.add_argument("--name", default="m3-baseline")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--hub", action="store_true", help="also write Hubverse-layout model output to evaluation/hub/ (large)")
    args = ap.parse_args(argv)
    global HUB_DIR
    if args.hub:
        HUB_DIR = Path(__file__).resolve().parent / "hub"

    if args.units == "db":
        from db.session import SessionLocal
        with SessionLocal() as s:
            units = eth.units_from_db(s, level=3)
    else:
        units = eth.synthetic_units(60 if args.quick else args.n)
    scenarios = ([Scenario("quick", years=8, burn_in_years=3)] if args.quick else DEFAULT_SCENARIOS)
    results = [run_scenario(units, sc) for sc in scenarios]
    out = {"name": args.name, "date": date.today().isoformat(), "synthetic_units": units.synthetic, "results": results}
    if not args.no_write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        stem = REPORTS / f"{date.today().isoformat()}-{args.name}"
        stem.with_suffix(".json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
        stem.with_suffix(".md").write_text(markdown(results, units, args.name), encoding="utf-8")
        print(f"Wrote {stem}.md")
    for r in results:
        d = r["detection"]
        print(f"{r['scenario']['name']}: action sens all {_f(d['action_all']['sensitivity'], True)} / large "
              f"{_f(d['action_large']['sensitivity'], True)}, PPV {_f(d['action_all']['ppv'], True)}")
        for tkey in ("high_burden_next_quarter", "ignition_next_quarter"):
            pk = r["risk"][tkey]["precision_at_k"]
            print(f"   {tkey}: " + ", ".join(f"{k} {_f(v, True)}" for k, v in pk.items()))
    return out


if __name__ == "__main__":
    main()
