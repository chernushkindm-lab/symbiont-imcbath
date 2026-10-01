"""Versioned inventory balances. L, h, g or mmol; no implicit missing-to-zero repair.

Inputs must be already aligned and quality gated by M02/M09. Streams are interval
averages; impulses are integrated quantities counted once, separately from streams.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Mapping, Sequence

EQUATION_VERSION = "inventory-1.0"
R_L_ATM_MOL_K = 0.082057366080960


def finite(value: float, name: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if value is None or not isfinite(value):
        raise ValueError(f"{name}: finite evidence required; missing is not zero")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError(f"{name}: invalid sign")
    return float(value)


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self):
        finite(self.lower, "lower")
        finite(self.upper, "upper")
        if self.lower > self.upper:
            raise ValueError("interval endpoints reversed")

    def __add__(self, other: Interval) -> Interval:
        return Interval(self.lower + other.lower, self.upper + other.upper)

    def __sub__(self, other: Interval) -> Interval:
        return Interval(self.lower - other.upper, self.upper - other.lower)

    def scale(self, factor: float) -> Interval:
        values = (self.lower * finite(factor, "factor"), self.upper * factor)
        return Interval(min(values), max(values))

    def divide(self, denominator: Interval, threshold: float = 1e-12) -> Interval:
        if denominator.lower <= threshold:
            raise ValueError("denominator interval includes zero or is not informative")
        values = [a / b for a in (self.lower, self.upper) for b in (denominator.lower, denominator.upper)]
        return Interval(min(values), max(values))


@dataclass(frozen=True)
class Stream:
    flow_l_h: float
    concentration: float
    evidence_id: str = ""
    basis: str = "g/L"

    def rate(self) -> float:
        return finite(self.flow_l_h, "delivered flow", nonnegative=True) * finite(self.concentration, "concentration", nonnegative=True)


def inventory_balance(*, volume_start_l: float, volume_end_l: float,
                      concentration_start: float, concentration_end: float,
                      elapsed_h: float, incoming: Sequence[Stream], outgoing: Sequence[Stream],
                      added_quantity: float = 0., removed_quantity: float = 0.,
                      concentration_unit: str = "mmol/L") -> dict:
    """Apparent disappearance, not automatically cellular uptake.

    For interval average flow products use their integrated mean, NOT the product
    of separately averaged flow and concentration. Caller owns that integration.
    """
    dt = finite(elapsed_h, "elapsed_h", positive=True)
    v0 = finite(volume_start_l, "volume_start_l", positive=True)
    v1 = finite(volume_end_l, "volume_end_l", positive=True)
    c0 = finite(concentration_start, "concentration_start", nonnegative=True)
    c1 = finite(concentration_end, "concentration_end", nonnegative=True)
    if concentration_unit not in {"mmol/L", "mg/L", "g/L"}:
        raise ValueError("unsupported concentration basis")
    if any(s.basis != concentration_unit for s in (*incoming, *outgoing)):
        raise ValueError("all streams must use the same explicit concentration basis")
    rin, rout = sum(s.rate() for s in incoming), sum(s.rate() for s in outgoing)
    addition = finite(added_quantity, "added quantity", nonnegative=True)
    removal = finite(removed_quantity, "removed quantity", nonnegative=True)
    accumulation = (v1 * c1 - v0 * c0) / dt
    return {"accumulation_per_h": accumulation,
            "incoming_per_h": rin + addition / dt, "outgoing_per_h": rout + removal / dt,
            "apparent_disappearance_per_h": rin - rout + (addition - removal) / dt - accumulation,
            "unit": concentration_unit.replace("/L", "/h"),
            "classification": "recalculated", "interpretation": "unresolved physical and biological sinks",
            "equation_version": EQUATION_VERSION,
            "parent_evidence": [s.evidence_id for s in (*incoming, *outgoing) if s.evidence_id]}


def biomass_productivity(*, volume_start_l: float, volume_end_l: float,
                         concentration_start_g_l: float, concentration_end_g_l: float,
                         elapsed_h: float, incoming: Sequence[Stream], outgoing: Sequence[Stream],
                         mean_volume_l: float, harvested_mass_g: float | None = None,
                         added_mass_g: float = 0., removed_mass_g: float = 0.,
                         endpoint: str = "total_dry_residue") -> dict:
    """Interval mean formation is total formation / integral(V dt), g/(L h).

    For total dry residue this is apparent residue formation, not cellular growth.
    Harvested mass is a subset of already-accounted outgoing mass, not added twice.
    """
    mean_v = finite(mean_volume_l, "mean volume", positive=True)
    b = inventory_balance(volume_start_l=volume_start_l, volume_end_l=volume_end_l,
                          concentration_start=concentration_start_g_l, concentration_end=concentration_end_g_l,
                          elapsed_h=elapsed_h, incoming=incoming, outgoing=outgoing,
                          added_quantity=added_mass_g, removed_quantity=removed_mass_g,
                          concentration_unit="g/L")
    result = {"net_accumulation_g_h": b["accumulation_per_h"],
              "net_formation_g_l_h": -b["apparent_disappearance_per_h"] / mean_v,
              "harvest_productivity_g_l_h": None, "endpoint": endpoint,
              "equation_version": EQUATION_VERSION, "classification": "recalculated",
              "cellular_interpretation_supported": endpoint == "cellular_dry_mass",
              "parent_evidence": b["parent_evidence"]}
    if harvested_mass_g is not None:
        result["harvest_productivity_g_l_h"] = finite(harvested_mass_g, "harvested mass", nonnegative=True) / (elapsed_h * mean_v)
    return result


def bottle_delivery_l_h(start_mass_g: float, end_mass_g: float, elapsed_h: float,
                        density_g_ml: float, *, bottle_changed: bool = False) -> dict:
    """A bottle reset/refill blocks delivery inference; negative delivery is forbidden."""
    a, b = finite(start_mass_g, "start mass", nonnegative=True), finite(end_mass_g, "end mass", nonnegative=True)
    dt, rho = finite(elapsed_h, "elapsed_h", positive=True), finite(density_g_ml, "density", positive=True)
    if bottle_changed or b > a:
        return {"flow_l_h": None, "status": "blocked", "reason": "bottle_change_or_mass_increase"}
    return {"flow_l_h": (a - b) / (rho * 1000 * dt), "status": "conditional",
            "assumption": "mass decrease is delivered liquid; no evaporation, spill or tare change"}


def element_mmol_from_solution(volume_ml: float, density_g_ml: float, solute_mass_fraction: float,
                               molar_mass_g_mol: float, atoms_per_molecule: int) -> float:
    if not 0 <= solute_mass_fraction <= 1 or atoms_per_molecule < 1:
        raise ValueError("explicit solute purity and elemental stoichiometry required")
    return (finite(volume_ml, "volume", nonnegative=True) * finite(density_g_ml, "density", positive=True)
            * solute_mass_fraction / finite(molar_mass_g_mol, "molar mass", positive=True) * atoms_per_molecule * 1000)


def gas_volume_to_mmol_h(flow_l_h: float, *, pressure_atm: float, temperature_k: float,
                         compressibility: float = 1., volume_basis: str) -> float:
    if volume_basis not in {"actual", "standard", "normal"}:
        raise ValueError("meter volume reference must be explicit")
    return (1000 * finite(flow_l_h, "gas flow", nonnegative=True) * finite(pressure_atm, "absolute pressure", positive=True)
            / (finite(compressibility, "compressibility", positive=True) * R_L_ATM_MOL_K
               * finite(temperature_k, "meter reference temperature", positive=True)))


def composition_gate(fractions: Mapping[str, float], *, complete: bool = False,
                     tolerance: float = .002, basis: str = "dry_mole_fraction") -> list[str]:
    reasons = []
    if basis != "dry_mole_fraction":
        reasons.append("gas_basis_unresolved_or_wet")
    if not fractions or any(v is None or not isfinite(v) or not 0 <= v <= 1 for v in fractions.values()):
        return reasons + ["missing_or_invalid_fraction"]
    total = sum(fractions.values())
    if total > 1 + tolerance:
        reasons.append("gas_composition_sum_above_one")
    if complete and abs(total - 1) > tolerance:
        reasons.append("incomplete_composition")
    return reasons


def conditional_exhaust_flow(inlet_total_mmol_h: Interval | None, *,
                            methane_uptake_mmol_h: Interval | None = None,
                            oxygen_uptake_mmol_h: Interval | None = None,
                            co2_generation_mmol_h: Interval | None = None,
                            total_inventory_change_mmol_h: Interval | None = None,
                            assumptions: Sequence[str] = ()) -> dict:
    """Fout=Fin-U_CH4-U_O2+G_CO2-dN/dt; inlet alone does not identify Fout.

    Intervals are bounded assumptions, not statistical confidence intervals. All
    other gas species must be conserved or represented in the inventory term.
    """
    inputs = (inlet_total_mmol_h, methane_uptake_mmol_h, oxygen_uptake_mmol_h,
              co2_generation_mmol_h, total_inventory_change_mmol_h)
    if any(x is None for x in inputs) or not assumptions:
        return {"status": "not_identifiable", "exhaust_mmol_h": None,
                "reason": "inlet-only data need independent closure or declared uptake/generation/storage bounds"}
    if any(x.lower < 0 for x in inputs[:4]):
        raise ValueError("inlet, uptake and generation intervals must be nonnegative")
    result = inputs[0] - inputs[1] - inputs[2] + inputs[3] - inputs[4]
    if result.lower <= 0:
        return {"status": "inconsistent_or_uninformative", "exhaust_mmol_h": None,
                "unconstrained_interval": asdict(result), "assumptions": list(assumptions)}
    return {"status": "model_only", "classification": "predicted", "exhaust_mmol_h": asdict(result),
            "uncertainty_kind": "scenario_bounds", "independent_validation": False,
            "assumptions": list(assumptions), "equation_version": "exhaust-total-1.0"}


def tracer_exhaust_flow(inert_inlet_mmol_h: Interval, inert_fraction: Interval, *,
                       conservation_evidence: str | None, inventory_and_leak_correction_mmol_h: Interval,
                       nitrogen_included: bool = False, nitrogen_conservation_verified: bool = False) -> dict:
    if not conservation_evidence or nitrogen_included and not nitrogen_conservation_verified:
        return {"status": "blocked", "reason": "tracer_conservation_not_established"}
    if not 0 < inert_fraction.lower <= inert_fraction.upper <= 1:
        return {"status": "blocked", "reason": "uninformative_tracer_denominator"}
    corrected = inert_inlet_mmol_h - inventory_and_leak_correction_mmol_h
    if corrected.lower <= 0:
        return {"status": "blocked", "reason": "nonpositive_tracer_flux"}
    return {"status": "conditional", "exhaust_mmol_h": asdict(corrected.divide(inert_fraction)),
            "uncertainty_kind": "bounded_input_uncertainty", "evidence": conservation_evidence}


def gas_fluxes(inlet_species_mmol_h: Mapping[str, float], outlet_fractions: Mapping[str, float], *,
               exhaust_mmol_h: float | None, exhaust_evidence: str | None,
               inventory_plus_liquid_correction_mmol_h: Mapping[str, float] | None,
               basis: str = "dry_mole_fraction", model_only_exhaust: bool = False) -> dict:
    reasons = composition_gate(outlet_fractions, basis=basis)
    species = ("CH4", "O2", "CO2")
    if any(s not in inlet_species_mmol_h or s not in outlet_fractions for s in species):
        reasons.append("missing_species")
    if exhaust_mmol_h is None or not exhaust_evidence:
        reasons.append("missing_exhaust_closure")
    if inventory_plus_liquid_correction_mmol_h is None or any(s not in inventory_plus_liquid_correction_mmol_h for s in species):
        reasons.append("inventory_and_liquid_terms_unresolved")
    if reasons:
        return {"status": "blocked", "reasons": reasons, "MUR": None, "OUR": None, "CER": None}
    fout = finite(exhaust_mmol_h, "exhaust flow", positive=True)
    rates = {s: finite(inlet_species_mmol_h[s], s + " input", nonnegative=True) - fout * outlet_fractions[s]
                - finite(inventory_plus_liquid_correction_mmol_h[s], s + " inventory correction") for s in species}
    mur, our, cer = rates["CH4"], rates["O2"], -rates["CO2"]
    if mur < -1e-9 or our < -1e-9:
        return {"status": "inconsistent", "reasons": ["negative_apparent_uptake"], "MUR": mur, "OUR": our, "CER": cer}
    return {"status": "model_only" if model_only_exhaust else "conditional",
            "MUR": mur, "OUR": our, "CER": cer, "rate_unit": "mmol/h",
            "OUR_over_MUR": our / mur if mur > 1e-9 else None,
            "MUR_over_OUR": mur / our if our > 1e-9 else None,
            "RQ_CER_over_OUR": cer / our if our > 1e-9 else None,
            "interpretation": "apparent species disappearance/production; not assigned to organisms",
            "exhaust_evidence": exhaust_evidence}


def oxygen_transfer(kla_h: float, equilibrium_mmol_l: float, dissolved_mmol_l: float, volume_l: float) -> dict:
    volumetric = finite(kla_h, "kLa", nonnegative=True) * (finite(equilibrium_mmol_l, "equilibrium", nonnegative=True)
                                                          - finite(dissolved_mmol_l, "dissolved oxygen", nonnegative=True))
    return {"volumetric_mmol_l_h": volumetric, "total_mmol_h": volumetric * finite(volume_l, "volume", positive=True)}


def do_air_saturation_to_mmol_l(percent: float, *, calibrated_air_saturation_mg_l: float) -> float:
    """Reference must match probe temperature/pressure/salinity calibration; >100% is allowed."""
    return finite(percent, "DO percent", nonnegative=True) / 100 * finite(calibrated_air_saturation_mg_l, "air reference", positive=True) / 31.998


def specific_cellular_uptake(apparent_mmol_h: Interval, biomass_g: Interval, *,
                             cellular_sink_supported: bool, cellular_mass_supported: bool,
                             minimum_biomass_g: float = .01) -> dict:
    """Do not turn total residue or unresolved disappearance into cellular q."""
    if not cellular_sink_supported or not cellular_mass_supported:
        return {'status': 'blocked', 'q_mmol_g_h': None,
                'reason': 'cellular_sink_and_mass_basis_required'}
    if apparent_mmol_h.lower < 0 or biomass_g.lower <= minimum_biomass_g:
        return {'status': 'blocked', 'q_mmol_g_h': None,
                'reason': 'uptake_or_biomass_interval_not_informative'}
    return {'status': 'conditional', 'q_mmol_g_h': asdict(apparent_mmol_h.divide(biomass_g, minimum_biomass_g)),
            'uncertainty_kind': 'bounded_input_uncertainty'}
