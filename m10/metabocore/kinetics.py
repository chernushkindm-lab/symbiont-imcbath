"""Independent, explicitly unqualified kinetic branch derived from notebook concepts.

State: [cellular dry mass g/L, CH4 g/L, O2 g/L, CO2 g/L, liquid volume L].
Pressure/solubility are boundary inputs; there is no hardware controller. Total
dry residue cannot validate this cellular state without an observation bridge.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Sequence

from .balances import finite


@dataclass(frozen=True)
class KineticParameters:
    mu_max_h: float
    ks_ch4_g_l: float
    ks_o2_g_l: float
    yield_x_ch4_g_g: float
    yield_x_o2_g_g: float
    biomass_carbon_fraction: float
    loss_h: float = 0.
    ki_o2_g_l: float | None = None
    ki_co2_g_l: float | None = None
    version: str = "hypothetical-not-fitted-v1"
    provenance: str = "explicit user scenario; parameters not estimated from history"

    def __post_init__(self):
        for key in ("mu_max_h", "ks_ch4_g_l", "ks_o2_g_l", "yield_x_ch4_g_g", "yield_x_o2_g_g"):
            finite(getattr(self, key), key, positive=True)
        finite(self.loss_h, "loss_h", nonnegative=True)
        if not 0 < self.biomass_carbon_fraction < 1:
            raise ValueError("biomass carbon fraction required")
        if self.co2_per_biomass_g_g < 0:
            raise ValueError("methane yield exceeds carbon conservation")
        for key in ("ki_o2_g_l", "ki_co2_g_l"):
            if getattr(self, key) is not None:
                finite(getattr(self, key), key, positive=True)

    @property
    def co2_per_biomass_g_g(self):
        # CH4 carbon consumed minus biomass C. Other products are explicitly absent.
        return (12.011 / (16.043 * self.yield_x_ch4_g_g) - self.biomass_carbon_fraction) * 44.009 / 12.011


@dataclass(frozen=True)
class BoundaryConditions:
    feed_l_h: float
    outflow_l_h: float
    evaporation_l_h: float
    feed_x_g_l: float
    feed_ch4_g_l: float
    feed_o2_g_l: float
    feed_co2_g_l: float
    cstar_ch4_g_l: float
    cstar_o2_g_l: float
    cstar_co2_g_l: float
    kla_ch4_h: float
    kla_o2_h: float
    kla_co2_h: float
    max_ch4_transfer_g_h: float
    max_o2_transfer_g_h: float
    label: str = "assumed held boundary; not observed future controls"

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key != "label":
                finite(value, key, nonnegative=True)


@dataclass(frozen=True)
class LiquidEvent:
    time_h: float
    removed_l: float
    added_l: float
    added_x_g_l: float = 0.
    added_ch4_g_l: float = 0.
    added_o2_g_l: float = 0.
    added_co2_g_l: float = 0.
    evidence_id: str = ""

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key != "evidence_id":
                finite(value, key, nonnegative=True)


def mu_from(ch4_g_l: float, o2_g_l: float, co2_g_l: float, p: KineticParameters) -> float:
    ch4, o2, co2 = max(ch4_g_l, 0.), max(o2_g_l, 0.), max(co2_g_l, 0.)
    oxygen_denominator = p.ks_o2_g_l + o2 + (o2 * o2 / p.ki_o2_g_l if p.ki_o2_g_l else 0.)
    return p.mu_max_h * ch4 / (p.ks_ch4_g_l + ch4) * o2 / oxygen_denominator / (1 + co2 / p.ki_co2_g_l if p.ki_co2_g_l else 1.)


def cstars_from(*, partial_pressure_atm: Sequence[float], henry_g_l_atm: Sequence[float]) -> tuple[float, ...]:
    """Species-specific Henry coefficients supplied with their documented conditions."""
    if len(partial_pressure_atm) != 3 or len(henry_g_l_atm) != 3:
        raise ValueError("CH4/O2/CO2 species-specific values required")
    return tuple(finite(a, "partial pressure", nonnegative=True) * finite(b, "Henry coefficient", positive=True)
                 for a, b in zip(partial_pressure_atm, henry_g_l_atm))


def rhs(time_h: float, state: Sequence[float], p: KineticParameters, b: BoundaryConditions) -> list[float]:
    """Pure ODE function; growth and both substrate demands share one growth rate.

    No uptake-only clipping can leave unsupported biomass formation. Saturation
    kinetics make growth vanish at a depleted CH4/O2 boundary. Reversible transfer
    includes stripping. Loss is an untracked detritus sink, not gas mineralisation.
    """
    if len(state) != 5 or any(not isfinite(x) for x in state):
        raise ValueError("finite five-state vector required")
    x, ch4, o2, co2 = (max(float(v), 0.) for v in state[:4])
    volume = finite(float(state[4]), "volume", positive=True)
    growth = mu_from(ch4, o2, co2, p) * x
    methane_transfer = min(b.kla_ch4_h * (b.cstar_ch4_g_l - ch4), b.max_ch4_transfer_g_h / volume)
    oxygen_transfer = min(b.kla_o2_h * (b.cstar_o2_g_l - o2), b.max_o2_transfer_g_h / volume)
    co2_transfer = b.kla_co2_h * (b.cstar_co2_g_l - co2)
    dilution, concentration_by_evaporation = b.feed_l_h / volume, b.evaporation_l_h / volume
    return [growth - p.loss_h * x + dilution * (b.feed_x_g_l - x) + concentration_by_evaporation * x,
            methane_transfer - growth / p.yield_x_ch4_g_g + dilution * (b.feed_ch4_g_l - ch4) + concentration_by_evaporation * ch4,
            oxygen_transfer - growth / p.yield_x_o2_g_g + dilution * (b.feed_o2_g_l - o2) + concentration_by_evaporation * o2,
            co2_transfer + growth * p.co2_per_biomass_g_g + dilution * (b.feed_co2_g_l - co2) + concentration_by_evaporation * co2,
            b.feed_l_h - b.outflow_l_h - b.evaporation_l_h]


def apply_event(state: Sequence[float], event: LiquidEvent) -> list[float]:
    if len(state) != 5 or any(not isfinite(v) or v < 0 for v in state) or state[4] <= 0:
        raise ValueError("invalid state")
    volume = state[4]
    if event.removed_l > volume:
        raise ValueError("event removes more liquid than available")
    new_volume = volume - event.removed_l + event.added_l
    if new_volume <= 0:
        raise ValueError("empty vessel requires a separately initialized segment")
    additions = (event.added_x_g_l, event.added_ch4_g_l, event.added_o2_g_l, event.added_co2_g_l)
    return [(state[i] * (volume - event.removed_l) + additions[i] * event.added_l) / new_volume
            for i in range(4)] + [new_volume]


def simulate(initial_state: Sequence[float], times_h: Sequence[float], p: KineticParameters,
             boundary: BoundaryConditions, *, events: Sequence[LiquidEvent] = (),
             rtol: float = 1e-7, atol: float = 1e-10) -> dict:
    """BDF integration restarted exactly at discrete events; returned event points are post-event.

    Piecewise observed controls should use consecutive calls with separate
    boundaries; no automatic interpolation across a control/event boundary.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    times = [finite(t, "time", nonnegative=True) for t in times_h]
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("strictly increasing time axis required")
    y = np.asarray(initial_state, dtype=float)
    if y.shape != (5,) or not np.isfinite(y).all() or (y < 0).any() or y[4] <= 0:
        raise ValueError("nonnegative concentrations and positive volume required")
    finite(rtol, "relative tolerance", positive=True)
    finite(atol, "absolute tolerance", positive=True)
    if any(e.time_h < times[0] or e.time_h > times[-1] for e in events):
        raise ValueError("event outside integration interval")
    by_time = {}
    for event in events:
        by_time.setdefault(event.time_h, []).append(event)
    for event in by_time.get(times[0], []):
        y = np.asarray(apply_event(y, event))
    outputs = {times[0]: y.tolist()}
    start = times[0]
    evaluations = 0
    for stop in sorted(set(times[1:]) | set(by_time)):
        if stop <= start:
            continue
        end_volume = y[4] + rhs(start, y, p, boundary)[4] * (stop - start)
        if end_volume <= 0:
            raise ValueError("boundary empties vessel; stop at a valid event")
        result = solve_ivp(lambda t, z: rhs(t, z, p, boundary), (start, stop), y,
                           method="BDF", rtol=rtol, atol=atol, t_eval=[stop])
        if not result.success:
            raise RuntimeError("kinetic solver failed: " + result.message)
        evaluations += result.nfev
        y = result.y[:, -1]
        # Tiny numerical excursions only, never a substantive clipping repair.
        if not np.isfinite(y).all() or np.any(y < -max(100 * atol, 1e-8)):
            raise RuntimeError("nonphysical solver state; tighten tolerances or revise model")
        y = np.maximum(y, 0.)
        for event in by_time.get(stop, []):
            y = np.asarray(apply_event(y, event))
        if stop in times:
            outputs[stop] = y.tolist()
        start = stop
    return {"times_h": times, "states": [outputs[t] for t in times],
            "state_columns": ["cellular_dry_mass_g_l", "ch4_g_l", "o2_g_l", "co2_g_l", "volume_l"],
            "classification": "predicted", "qualification": "hypothetical_unfitted",
            "observation_bridge_required": "cellular dry mass to total dry residue",
            "parameters": asdict(p), "boundary": asdict(boundary), "solver": "scipy.solve_ivp:BDF",
            "rtol": rtol, "atol": atol, "rhs_evaluations": evaluations,
            "events": [asdict(e) for e in events]}


def kinetic_input_gate(*, calibrated_air_reference: bool, methane_solubility_supported: bool,
                       transfer_conditions_matched: bool, cellular_residue_bridge: bool,
                       delivery_supported: bool, parameters_fitted: bool) -> dict:
    checks = locals().copy()
    missing = [key for key, value in checks.items() if not value]
    return {"qualified_forecast": False, "eligible_for_holdout_evaluation": not missing,
            "status": "blocked_for_qualification" if missing else "eligible_for_holdout_evaluation",
            "missing_evidence": missing, "conditional_scenario_available": True,
            "qualification_note": "Passing input checks still requires an independently accepted held-out evaluation."}


def kinetic_reference_case() -> dict:
    """Closed numerical reference, not historical data or cultivation guidance."""
    params = KineticParameters(mu_max_h=.2, ks_ch4_g_l=.0001, ks_o2_g_l=.0001,
                               yield_x_ch4_g_g=.5, yield_x_o2_g_g=.25,
                               biomass_carbon_fraction=.5)
    boundary = BoundaryConditions(feed_l_h=0., outflow_l_h=0., evaporation_l_h=0.,
                                  feed_x_g_l=0., feed_ch4_g_l=0., feed_o2_g_l=0., feed_co2_g_l=0.,
                                  cstar_ch4_g_l=0., cstar_o2_g_l=0., cstar_co2_g_l=0.,
                                  kla_ch4_h=0., kla_o2_h=0., kla_co2_h=0.,
                                  max_ch4_transfer_g_h=0., max_o2_transfer_g_h=0.,
                                  label='synthetic closed numerical reference; no LAB005 replay')
    result = simulate([.1, .001, .005, 0., 10.], [0., 1., 4., 12.], params, boundary)
    def carbon(state):
        x, ch4, _, co2, volume = state
        return volume * (x * params.biomass_carbon_fraction + ch4 * 12.011 / 16.043 + co2 * 12.011 / 44.009)
    carbon_initial = carbon(result['states'][0])
    rows = [dict(time_h=t, **dict(zip(result['state_columns'], state))) for t, state in zip(result['times_h'], result['states'])]
    return result | {'rows': rows, 'params': result['parameters'], 'classification': 'assumed/synthetic',
                     'qualification': 'numerical_reference_only',
                     'conservation': {'carbon_initial_g': carbon_initial,
                                      'maximum_carbon_residual_g': max(abs(carbon(s)-carbon_initial) for s in result['states']),
                                      'tolerance_g': 1e-8,
                                      'meaning': 'methane/biomass/CO2 carbon only; no nitrogen or full elemental closure asserted'},
                     'historical_validation': False}
