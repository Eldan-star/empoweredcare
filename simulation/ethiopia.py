"""
Synthetic Ethiopian measles data for evaluation (SYSTEM_SPEC section 10, METHODOLOGY
section 5).

Three layers:
1. Units: real OCHA units from the database when loaded (`units_from_db`), or a seeded
   synthetic geography of the same scale (`synthetic_units`) for tests.
2. True transmission: IDM's laser-measles biweekly SIR model (`simulate`). laser-measles
   is installed separately (requirements-sim.txt), because its numerical stack is pinned
   differently from the web app's.
3. Reporting (ours, `report`): per-unit reporting rates, 0-4 week delays, missing weeks and
   late batch backfills, so detection is tested on data that looks like PHEM data, not on
   the truth.

Everything is seeded; the same seed gives the same data.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

CRUDE_BIRTH_RATE = 31.9   # per 1,000 per year, Ethiopia 2023 (World Bank, SP.DYN.CBRT.IN)
CRUDE_DEATH_RATE = 6.0    # per 1,000 per year, approximate; affects only population turnover


@dataclass
class Units:
    pcodes: list[str]
    lat: np.ndarray
    lon: np.ndarray
    population: np.ndarray
    mcv1: np.ndarray
    mcv2: np.ndarray
    region: list[str]
    synthetic: bool = True


def synthetic_units(n: int = 400, seed: int = 0, regions: int = 12, median_pop: int = 100_000) -> Units:
    """A seeded stand-in for Ethiopian woredas (EPHI applies measles thresholds at woreda
    level): units clustered into regions across Ethiopia's bounding box, log-normal
    populations around `median_pop` (the 1,148 OCHA woredas average ~100,000), and MCV1 coverage
    that varies by region (between-region spread wider than within-region), as in the
    IHME subnational estimates. Illustrative only, not real data."""
    rng = np.random.default_rng(seed)
    centres = np.column_stack([rng.uniform(4.5, 13.5, regions), rng.uniform(35.0, 46.0, regions)])
    region_cov = rng.beta(5, 3, regions)                       # region mean MCV1 ~0.6
    which = rng.integers(0, regions, n)
    lat = centres[which, 0] + rng.normal(0, 0.6, n)
    lon = centres[which, 1] + rng.normal(0, 0.6, n)
    pop = np.round(rng.lognormal(np.log(median_pop), 0.5, n)).astype(int)
    mcv1 = np.clip(region_cov[which] + rng.normal(0, 0.08, n), 0.1, 0.97)
    mcv2 = np.clip(mcv1 * rng.uniform(0.5, 0.8, n), 0, mcv1)
    return Units([f"SYN{i:03d}" for i in range(n)], lat, lon, pop, mcv1, mcv2,
                 [f"R{r:02d}" for r in which], synthetic=True)


def units_from_db(session, level: int = 2, mcv1: Optional[dict] = None, mcv2: Optional[dict] = None,
                  seed: int = 0) -> Units:
    """Real OCHA units (P-codes, centroids, populations) from the database. Coverage comes
    from the given dicts (pcode -> 0-1), else the latest `immunization` rows, else a seeded
    synthetic value (reported in the evaluation output)."""
    from sqlalchemy import select
    from db.models import Immunization, OrgUnit
    rows = session.scalars(select(OrgUnit).where(OrgUnit.level == level, OrgUnit.population.is_not(None),
                                                 OrgUnit.lat.is_not(None))).all()
    if not rows:
        raise RuntimeError(f"No level-{level} units with population and centroid; load the OCHA boundaries first")
    imm = {}
    for r in session.scalars(select(Immunization).order_by(Immunization.year, Immunization.month)):
        imm[r.pcode] = r
    rng = np.random.default_rng(seed)
    synthetic = False
    m1, m2 = [], []
    for u in rows:
        c1 = (mcv1 or {}).get(u.pcode) or (imm[u.pcode].mcv1_coverage if u.pcode in imm else None)
        c2 = (mcv2 or {}).get(u.pcode) or (imm[u.pcode].mcv2_coverage if u.pcode in imm else None)
        if c1 is None:
            synthetic = True
            c1 = float(np.clip(rng.beta(5, 3), 0.1, 0.97))
        m1.append(c1)
        m2.append(min(c2 if c2 is not None else c1 * 0.6, c1))
    return Units([u.pcode for u in rows], np.array([u.lat for u in rows]), np.array([u.lon for u in rows]),
                 np.array([u.population for u in rows]), np.array(m1), np.array(m2),
                 [u.parent_pcode or "" for u in rows], synthetic=synthetic)


@dataclass
class Truth:
    start: date                 # Monday of the first week
    weekly_infections: np.ndarray   # (weeks, units)
    biweekly_susceptibles: np.ndarray
    mixing: str
    params: dict = field(default_factory=dict)

    @property
    def weeks(self) -> int:
        return self.weekly_infections.shape[0]

    def week_key(self, w: int) -> tuple[int, int]:
        y, k, _ = (self.start + timedelta(weeks=w)).isocalendar()
        return y, k


def simulate(units: Units, years: int = 12, mixing: str = "gravity", seed: int = 1,
             beta_scale: float = 1.0, seasonality: float = 0.15, importation_rate: float = 0.2,
             r0: Optional[float] = None, start: date = date(2014, 1, 6)) -> Truth:
    """Run laser-measles (biweekly SIR) and split each 14-day tick into two weeks.

    mixing: "gravity" (laser default exponents), "radiation" or "stouffer" (intervening
    opportunities) - the last two
    deliberately differ from the gravity form our risk model assumes (mis-specification
    tests, METHODOLOGY section 5)."""
    import polars as pl
    from laser.measles import create_component
    from laser.measles.base import BaseComponent
    from laser.measles.biweekly import BiweeklyModel, BiweeklyParams
    from laser.measles.biweekly import components as c
    from laser.measles.mixing.gravity import GravityMixing
    from laser.measles.mixing.radiation import RadiationMixing
    from laser.measles.mixing.stouffer import StoufferMixing

    class Recorder(BaseComponent):
        def __init__(self, model, verbose: bool = False):
            super().__init__(model, verbose)
            self.infections, self.susceptibles = [], []

        def __call__(self, model, tick):
            # In the biweekly model I holds the infections of the latest tick.
            self.infections.append(model.patches.states.I.copy())
            self.susceptibles.append(model.patches.states.S.copy())

    df = pl.DataFrame({"id": units.pcodes, "lat": units.lat.astype(float), "lon": units.lon.astype(float),
                       "pop": units.population.astype(int), "mcv1": units.mcv1.astype(float)})
    ticks = 26 * years
    model = BiweeklyModel(df, BiweeklyParams(num_ticks=ticks, seed=seed, start_time=start.strftime("%Y-%m"),
                                             show_progress=False))
    mixer = {"gravity": GravityMixing, "radiation": RadiationMixing, "stouffer": StoufferMixing}[mixing]()
    infection = c.InfectionParams(seasonality=seasonality, mixer=mixer)
    infection = c.InfectionParams(seasonality=seasonality, mixer=mixer, beta=infection.beta * beta_scale)
    # Start near the endemic equilibrium implied by the transmission rate (one 14-day tick
    # of infectiousness, so R0 = beta per day x 14), not an unrelated R0, to avoid a long
    # artificial transient.
    r0 = r0 or infection.beta * 14
    model.components = [
        create_component(c.InitializeEquilibriumStatesProcess, c.InitializeEquilibriumStatesParams(R0=r0)),
        create_component(c.VitalDynamicsProcess, c.VitalDynamicsParams(crude_birth_rate=CRUDE_BIRTH_RATE,
                                                                       crude_death_rate=CRUDE_DEATH_RATE)),
        create_component(c.ImportationPressureProcess, c.ImportationPressureParams(crude_importation_rate=importation_rate)),
        create_component(c.InfectionProcess, infection),
        Recorder,
    ]
    model.run()
    rec = next(x for x in model.instances if isinstance(x, Recorder))
    bi = np.array(rec.infections, dtype=np.int64)               # (ticks, units)
    rng = np.random.default_rng(seed + 1000)
    first = rng.binomial(bi, 0.5)
    weekly = np.empty((2 * ticks, bi.shape[1]), dtype=np.int64)
    weekly[0::2], weekly[1::2] = first, bi - first
    return Truth(start, weekly, np.array(rec.susceptibles), mixing,
                 {"years": years, "seed": seed, "beta_scale": beta_scale, "seasonality": seasonality,
                  "importation_rate": importation_rate, "r0": r0})


@dataclass
class Reported:
    suspected: np.ndarray       # (weeks, units) as finally received; NaN = never reported
    confirmed: np.ndarray
    arrival_week: np.ndarray    # (weeks, units) week index when the report arrived
    reporting_rate: np.ndarray  # (units,) true per-unit reporting rate

    def as_of(self, t: int) -> tuple[np.ndarray, np.ndarray]:
        """What the system could see at the end of week t: weeks <= t whose report had
        arrived; later or never-received weeks are NaN (unreported)."""
        s = self.suspected[:t + 1].copy()
        c = self.confirmed[:t + 1].copy()
        late = self.arrival_week[:t + 1] > t
        s[late] = np.nan
        c[late] = np.nan
        return s, c


def report(truth: Truth, seed: int = 2, rate_mean: float = 0.12, rate_sd: float = 0.06,
           p_missing: float = 0.10, p_backfill: float = 0.15, delay_probs=(0.35, 0.35, 0.2, 0.1, 0.0),
           confirm_share: float = 0.3) -> Reported:
    """PHEM-like reported data from true infections.
    - Each unit reports a share of infections (Beta-distributed rate, mean `rate_mean`).
      Real Ethiopian rates are unknown; the evaluation varies this.
    - Each weekly report arrives 0-4 weeks late (`delay_probs`, SYSTEM_SPEC 10: 2-4 weeks
      typical at national level), `p_missing` of weeks never arrive, and `p_backfill` arrive
      in a batch 4-12 weeks late.
    - Confirmed = a share of reported cases (sampled and IgM-positive, or epi-linked)."""
    rng = np.random.default_rng(seed)
    W, U = truth.weekly_infections.shape
    a = rate_mean * (rate_mean * (1 - rate_mean) / rate_sd ** 2 - 1)
    b = a * (1 - rate_mean) / rate_mean
    rate = rng.beta(a, b, U)
    suspected = rng.binomial(truth.weekly_infections, rate[None, :]).astype(float)
    confirmed = rng.binomial(suspected.astype(np.int64), confirm_share).astype(float)
    delay = rng.choice(len(delay_probs), size=(W, U), p=np.array(delay_probs) / sum(delay_probs))
    backfill = rng.random((W, U)) < p_backfill
    delay[backfill] = rng.integers(4, 13, backfill.sum())
    arrival = np.arange(W)[:, None] + delay
    missing = rng.random((W, U)) < p_missing
    suspected[missing] = np.nan
    confirmed[missing] = np.nan
    arrival[missing] = np.iinfo(np.int32).max
    return Reported(suspected, confirmed, arrival, rate)


def outbreak_onsets(truth: Truth, population: np.ndarray, per_100k: float = 20.0,
                    quiet_per_100k: float = 5.0, quiet_weeks: int = 8) -> list[tuple[int, int, float]]:
    """True outbreak onsets as (week, unit, size): the first week the 4-week true infection
    count reaches `per_100k` per 100,000 after at least `quiet_weeks` weeks below
    `quiet_per_100k`. `size` is true infections per 100,000 in the 12 weeks from onset, so
    small flare-ups and large outbreaks can be scored separately. A definition for
    evaluation only, stated in the report. Units in continuous transmission never go quiet,
    so they have no onsets; the "high transmission" target covers them."""
    inf = truth.weekly_infections.astype(float)
    W, U = inf.shape
    roll = np.array([inf[max(0, t - 3):t + 1].sum(axis=0) for t in range(W)])
    rate = roll / population[None, :] * 1e5
    onsets = []
    for u in range(U):
        quiet = 0
        for t in range(W):
            if rate[t, u] >= per_100k and quiet >= quiet_weeks:
                size = inf[t:t + 12, u].sum() / population[u] * 1e5
                onsets.append((t, u, float(size)))
                quiet = 0
            quiet = quiet + 1 if rate[t, u] < quiet_per_100k else (0 if rate[t, u] >= per_100k else quiet)
    return onsets
