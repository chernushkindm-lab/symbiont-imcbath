"""Read-only LAB005 historical import. Supplied notebooks/formulas are never executed."""
from __future__ import annotations
import csv, hashlib, io, math, re, unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from .contracts import Observation, Run, SCHEMA_VERSION

PARSER_VERSION = "lab005.historical/1.0.0"
LAB_TZ = timezone(timedelta(hours=5), "Asia/Yekaterinburg")
EMPTY = {"", "-", "—", "–", "nan", "none", "null", "n/a"}
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

def _text(v):
    return "" if v is None else unicodedata.normalize("NFKC", str(v)).strip()
def _iso(v):
    return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if v else None
def _id(*parts):
    return hashlib.sha256("\x1f".join(str(x) for x in parts).encode()).hexdigest()[:24]
def _cell(col, row):
    label = ""
    while col:
        col, rem = divmod(col - 1, 26)
        label = chr(65 + rem) + label
    return f"{label}{row}"

def parse_number(raw):
    """Never coerce missing/error values or censored assays to a point estimate."""
    out = dict(value=None, lower_bound=None, upper_bound=None, censoring=None, qc_flags=[])
    s = _text(raw)
    if isinstance(raw, bool):
        out["qc_flags"] = ["non_numeric"]
    elif s.lower() in EMPTY:
        out["qc_flags"] = ["missing"]
    elif s.startswith("#"):
        out["qc_flags"] = ["spreadsheet_error"]
    elif re.search(r"(?:ПС|КПС|МЭ|NH|KOH)\s*\d+", s, re.I):
        out["qc_flags"] = ["identifier_in_numeric_cell"]
    else:
        s = s.replace("\u00a0", "").replace(" ", "").replace(",", ".").replace("−", "-")
        interval = re.fullmatch(rf"({NUMBER})[-–—]({NUMBER})", s)
        censored = re.fullmatch(rf"([<>≤≥]=?)({NUMBER})", s)
        plus = re.fullmatch(rf"({NUMBER})\+", s)
        if re.fullmatch(NUMBER, s):
            value = float(s)
            if math.isfinite(value):
                out["value"] = value
            else:
                out["qc_flags"] = ["nonfinite"]
        elif interval:
            lo, hi = map(float, interval.groups())
            if lo <= hi:
                out.update(lower_bound=lo, upper_bound=hi, censoring="interval", qc_flags=["censored"])
            else:
                out["qc_flags"] = ["invalid_interval"]
        elif censored:
            symbol, val = censored.groups()
            lower = symbol.startswith((">", "≥"))
            out["lower_bound" if lower else "upper_bound"] = float(val)
            out.update(censoring="right" if lower else "left", qc_flags=["censored"])
        elif plus:
            out.update(lower_bound=float(plus[1]), censoring="right", qc_flags=["censored"])
        else:
            out["qc_flags"] = ["unresolved_numeric_annotation" if re.search(r"\d", s) else "non_numeric"]
    if any(v is not None and not math.isfinite(v) for v in (out["lower_bound"],out["upper_bound"])):
        out.update(value=None,lower_bound=None,upper_bound=None,censoring=None,qc_flags=["nonfinite"])
    return out

def parse_local_date(raw):
    if isinstance(raw, datetime):
        return raw.date() if raw.year >= 1950 else None
    if isinstance(raw, date):
        return raw if raw.year >= 1950 else None
    if isinstance(raw, (int, float)) and 18000 < raw < 100000:
        return (datetime(1899, 12, 30) + timedelta(days=float(raw))).date()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%d/%m/%Y"):
        try:
            value = datetime.strptime(_text(raw), fmt).date()
            return value if value.year >= 1950 else None
        except ValueError:
            pass
    return None

def parse_local_time(raw):
    flags = []
    if isinstance(raw, datetime):
        if raw.year < 1950:
            flags.append("excel_time_date_artifact")
        t = raw.time()
    elif isinstance(raw, time):
        t = raw
    elif isinstance(raw, (int, float)) and 0 <= raw < 1:
        t = (datetime(2000, 1, 1) + timedelta(days=float(raw))).time()
    else:
        t = None
        for fmt in ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f"):
            try:
                t = datetime.strptime(_text(raw), fmt).time()
                break
            except ValueError:
                pass
        if t is None:
            return None, ["missing_time" if not _text(raw) else "invalid_time"]
    if t.microsecond:
        seconds = t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6
        if abs(seconds - round(seconds)) <= .05:
            t = (datetime(2000, 1, 1) + timedelta(seconds=round(seconds) % 86400)).time()
            flags.append("excel_subsecond_rounding")
    return t, flags

def parse_timestamp(raw_date, raw_time):
    d = parse_local_date(raw_date)
    t, flags = parse_local_time(raw_time)
    if not d:
        flags.append("missing_date" if not _text(raw_date) else "invalid_or_incomplete_date")
    return (datetime.combine(d, t, LAB_TZ) if d and t else None), flags

def bounded_timestamps(rows, date_col=0, time_col=1, max_fill_rows=23):
    """Same-day date fill, max 23 hourly rows; never guess midnight rollover."""
    anchor, age, previous, result = None, 0, None, []
    for row in rows:
        raw_date = row[date_col] if date_col < len(row) else None
        raw_time = row[time_col] if time_col < len(row) else None
        d = parse_local_date(raw_date)
        t, flags = parse_local_time(raw_time)
        if _text(raw_date):
            anchor, age, previous = d, 0, None
            if not d:
                flags.append("invalid_or_incomplete_date")
        else:
            age += 1
            if anchor and t and age <= max_fill_rows and (previous is None or t >= previous):
                d = anchor
                flags.append("bounded_table_date_fill")
            else:
                flags.append("unresolved_date")
        if not t or (not _text(raw_date) and previous and t < previous):
            anchor, d = None, None
        if not any(_text(x) for x in row):
            anchor = None
        previous = t
        result.append((datetime.combine(d, t, LAB_TZ) if d and t else None, flags))
    return result

def _source(path, role, read_time=None):
    p = Path(path)
    checksum = hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(source_id="src-" + checksum[:20], filename=p.name, source_uri=p.resolve().as_uri(),
        sha256=checksum, bytes=p.stat().st_size, role=role, access_status="read", parser_version=PARSER_VERSION,
        read_time=read_time or _iso(datetime.now(timezone.utc)),
        source_modification_time=_iso(datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)),
        acquisition_time=None, availability_time=None, run_dates=[],
        original_policy="Immutable original; never modified or executed by importer")
def _read_csv(path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    return list(csv.reader(io.StringIO(text)))
def _locator(src, sheet, row, col=None):
    return dict(source_id=src["source_id"], sheet=sheet, row=row, column=col, cell=_cell(col,row) if col else None)
def _issue(code, severity, outputs, detail, evidence=None, resolution="open"):
    return dict(issue_id=code, severity=severity, affected_outputs=outputs, detail=detail,
                proposed_interpretation=detail, evidence=evidence, resolution_status=resolution)

# index, parameter, unit, classification, matrix, basis: independently reviewed maps.
PROTOCOL_MAP = {
2:("ph","pH","measured","broth","hydrogen-ion activity"),
3:("temperature_C","degC","measured","broth","temperature"),
4:("do_pct","%","measured","broth","user-confirmed percent air saturation; calibration conditions unresolved"),
5:("rpm","rpm","measured","broth","agitation"),
6:("volume_recorded_L","L","measured","broth","recorded working volume"),
7:("tds_ppm","ppm","measured","broth","TDS basis unresolved"),
8:("ph_control","pH","measured","broth","independent pH check"),
10:("feed_bottle_mass_g","g","measured","medium","gross bottle mass"),
11:("feed_bottle_residual_mass_g","g","measured","medium","mass before replacement"),
12:("feed_bottle_replacement_mass_g","g","measured","medium","mass after replacement"),
13:("legacy_feed_g_h","g/h","source-derived","medium","unvalidated bottle difference"),
15:("feed_concentration_factor","1","source-derived","medium","recipe multiplier"),
17:("feed_setpoint_mL_min","mL/min","setpoint","medium","pump command; not actual delivery"),
19:("nh_bottle_mass_g","g","measured","titrant","gross bottle mass"),
20:("nh_bottle_residual_mass_g","g","measured","titrant","mass before replacement"),
21:("nh_bottle_replacement_mass_g","g","measured","titrant","mass after replacement"),
22:("legacy_nh_g_h","g/h","source-derived","titrant","unvalidated bottle difference"),
25:("koh_bottle_mass_g","g","measured","titrant","gross bottle mass"),
26:("koh_bottle_residual_mass_g","g","measured","titrant","mass before replacement"),
27:("koh_bottle_replacement_mass_g","g","measured","titrant","mass after replacement"),
28:("legacy_koh_g_h","g/h","source-derived","titrant","unvalidated bottle difference"),
31:("legacy_dilution_h_inv","1/h","source-derived","broth","user-confirmed dilution D; calculation unvalidated"),
33:("inlet_air_L_min","L/min","measured","gas","standard/actual volume basis unresolved"),
34:("inlet_o2_L_min","L/min","measured","gas","concentrator stream; purity separate"),
35:("inlet_ch4_L_h","L/h","measured","gas","standard/actual volume basis unresolved"),
37:("offgas_o2_pct","%","measured","gas","wet/dry and calibration unresolved"),
38:("offgas_ch4_pct","%","measured","gas","wet/dry and calibration unresolved"),
39:("offgas_co2_pct","%","measured","gas","wet/dry and calibration unresolved"),
41:("od_fek","OD","measured","broth","FEK; wavelength/path/dilution unresolved"),
42:("od_mucheck_raw","OD","measured","broth","muCheck raw optical channel"),
43:("od_mucheck_converted","OD","source-derived","broth","legacy muCheck conversion"),
45:("legacy_mucheck_productivity_g_L_h","g/(L h)","source-derived","broth","legacy productivity"),
46:("legacy_productivity_g_L_h","g/(L h)","source-derived","broth","legacy productivity"),
48:("legacy_asv_g_L","g/L","source-derived","broth","OD conversion; not gravimetry"),
49:("legacy_mucheck_asv_g_L","g/L","source-derived","broth","OD conversion; not gravimetry"),
51:("legacy_otr_g_L_h","g/(L h)","source-derived","gas","exhaust unresolved"),
52:("legacy_otr_no_ch4_g_L_h","g/(L h)","source-derived","gas","methane neglected"),
54:("legacy_feed_n_mg_h","mg/h","source-derived","medium","elemental N; delivery unverified"),
55:("legacy_titrant_n_mg_h","mg/h","source-derived","titrant","elemental N; delivery unverified"),
56:("legacy_n_uptake_mg_h","mg/h","source-derived","broth","not validated cellular uptake"),
57:("legacy_p_input_mg_h","mg/h","source-derived","medium","elemental P; delivery unverified"),
58:("legacy_p_uptake_mg_h","mg/h","source-derived","broth","not validated cellular uptake"),
59:("legacy_n_p_ratio","1","source-derived","broth","legacy N:P basis unresolved"),
60:("legacy_feed_k_mg_h","mg/h","source-derived","medium","elemental K; delivery unverified"),
61:("legacy_titrant_k_mg_h","mg/h","source-derived","titrant","elemental K; delivery unverified"),
62:("legacy_mu_h_inv","1/h","source-derived","broth","legacy growth estimate"),
66:("legacy_feed_mL_min","mL/min","source-derived","medium","inferred; not verified delivery"),
67:("legacy_total_liquid_mL_min","mL/min","source-derived","broth","inferred feed plus titrant"),
69:("legacy_air_o2_L_min","L/min","source-derived","gas","air component; do not count twice"),
70:("o2_purity_pct","%","measured","gas","purity separate from flow"),
72:("legacy_ch4_L_min","L/min","source-derived","gas","duplicate methane L/h conversion"),
74:("legacy_titrant_nh4oh_pct","%","source-derived","titrant","NH4OH concentration basis unresolved")}
MAY_MAP={k:PROTOCOL_MAP[v] for k,v in {3:5,4:3,5:2,6:8,7:7,8:4,9:10,10:11,11:12,14:17,
15:66,16:67,17:31,18:33,19:34,20:70,22:19,23:20,24:21,26:25,27:26,28:27,35:6,36:15,
38:41,39:42,40:43,41:48,42:46,43:37,44:38,45:39,46:51,50:59,51:62}.items()}
MAY_MAP.update({21:("inlet_ch4_L_min","L/min","measured","gas","primary May header; report mL/min conflicts"),
25:("legacy_nh_mL_h","mL/h","source-derived","titrant","bottle difference/density unverified"),
29:("legacy_koh_mL_h","mL/h","source-derived","titrant","bottle difference/density unverified"),
47:("legacy_feed_n_mg_min","mg/min","source-derived","medium","elemental N; delivery unverified"),
48:("legacy_titrant_n_mg_min","mg/min","source-derived","titrant","elemental N; delivery unverified"),
49:("legacy_p_input_mg_min","mg/min","source-derived","medium","elemental P; delivery unverified")})


def _observation(run_id, src, sheet, row, col, raw, spec, stamp, flags=None, sample_id=None):
    param, unit, classification, matrix, basis = spec
    parsed = parse_number(raw)
    qc = list(dict.fromkeys((flags or []) + parsed.pop("qc_flags")))
    bad = any(f in qc for f in ("spreadsheet_error","identifier_in_numeric_cell","invalid_interval","non_numeric","nonfinite","unresolved_numeric_annotation"))
    value = parsed["value"]
    if value is not None and value < 0 and param not in ("temperature_C","legacy_mu_h_inv"):
        qc.append("negative_value")
        bad = True
        if param.startswith("legacy_") and ("g_h" in param or "mL_" in param):
            qc.append("negative_inferred_delivery")
    if param == "volume_recorded_L" and value is not None and value != 10:
        qc.append("volume_conflicts_authoritative_10_L")
    if param.startswith("offgas_") and value is not None and not 0 <= value <= 100:
        qc.append("gas_fraction_out_of_range")
        bad = True
    if classification == "source-derived":
        qc.append("unvalidated_source_calculation")
    ob = Observation(observation_id="obs-"+_id(src["source_id"],sheet,row,col,param),run_id=run_id,
        parameter_code=param,raw_value=str(raw) if isinstance(raw,(date,time)) else raw,raw_unit=unit,
        value=value,unit=unit,classification=classification,source_locator=_locator(src,sheet,row,col),
        event_time=_iso(stamp),local_time=stamp.isoformat() if stamp else None,basis=basis,matrix=matrix,
        sample_id=sample_id,sensor_id={"ph":"SEN-PH","temperature_C":"SEN-TEMP","do_pct":"SEN-O2","od_fek":"EQ-025","od_mucheck_raw":"EQ-016/EQ-017"}.get(param),
        qc_flags=qc,accepted=not bad and (value is not None or parsed["censoring"] is not None),
        lower_bound=parsed["lower_bound"],upper_bound=parsed["upper_bound"],censoring=parsed["censoring"],
        exclusion_reasons=[f for f in qc if f not in ("bounded_table_date_fill","excel_subsecond_rounding")] if bad else []).to_dict()
    ob["eligible_as_independent_validation"] = classification == "measured" and ob["accepted"]
    ob["eligible_for_forecast_input"] = False
    return ob

def read_calibration(path, read_time=None):
    import openpyxl
    src = _source(path,"authoritative OD-to-total-dry-residue calibration; separate telemetry",read_time)
    wb = openpyxl.load_workbook(path,data_only=True,read_only=True)
    rows = list(wb["Calibration"].values)
    labels = {str(r[0]):(i+1,r[1]) for i,r in enumerate(rows) if len(r)>1 and r[0] is not None}
    kr,k = labels["k chosen (g/L/OD)"]
    lr,lo = labels["Forced-zero k 95% CI low"]
    hr,hi = labels["Forced-zero k 95% CI high"]
    rr,rmse = labels["Forced-zero RMSE"]
    dishes = [dict(source_row=i+1,date=str(r[0]),dish_id=r[2],sample_volume_mL=r[3],od=r[4],
                   dish_g=r[5],dish_residue_g=r[6],residue_g_L=r[9],biological_sample_id=None,
                   replicate_group_candidate=f"{r[0]}:{r[4]}")
              for i,r in enumerate(rows) if len(r)>=12 and r[11]=="Y" and isinstance(r[4],(int,float))]
    telemetry = sorted({str(r[0]) for r in wb["Telemetry_Productivity"].iter_rows(min_row=6,values_only=True) if r and r[0]})
    wb.close()
    return dict(calibration_id="F10-total-dry-residue-"+src["sha256"][:12],source=src,
        coefficient=float(k),coefficient_unit="g/(L OD)",coefficient_ci95=[float(lo),float(hi)],
        rmse_g_L=float(rmse),endpoint="total_dry_residue",equation="X = k * OD",
        equation_version="od.total-dry-residue/1.0",availability_time=None,
        source_locator=_locator(src,"Calibration",kr,2),
        ci_locators=[_locator(src,"Calibration",lr,2),_locator(src,"Calibration",hr,2)],
        rmse_locator=_locator(src,"Calibration",rr,2),
        supported_od_range=[min(d["od"] for d in dishes),max(d["od"] for d in dishes)],
        dishes=dishes,dish_count=len(dishes),candidate_replicate_groups=len({d["replicate_group_candidate"] for d in dishes}),
        historical_telemetry_runs_excluded=telemetry,
        limitations=["dish-level CI is not biological-replicate CI","instrument/path/dilution comparability unverified",
                     "total dry residue may include medium solids","August use is cross-run calibration transfer"])

def _calibrated(ob, cal):
    out = dict(ob)
    od = ob["value"]
    out.update(observation_id="obs-"+_id(ob["observation_id"],cal["calibration_id"]),
        parameter_code="dry_residue_g_L",raw_unit="OD",unit="g/L",value=od*cal["coefficient"],
        classification="recalculated",basis="OD-derived total dry residue; not cellular DCW",
        calibration_version=cal["calibration_id"],parent_observation_ids=[ob["observation_id"]],
        equation_version=cal["equation_version"],eligible_as_independent_validation=False,
        uncertainty=dict(kind="coefficient_only_ci95",lower=od*cal["coefficient_ci95"][0],
            upper=od*cal["coefficient_ci95"][1],residual_rmse_g_L=cal["rmse_g_L"],
            warning="not a prediction interval; shared calibration/transfer uncertainty remains"))
    out["qc_flags"] = list(ob["qc_flags"])+["calibration_transfer_unverified","total_dry_residue_not_cellular_dcw"]
    if not cal["supported_od_range"][0] <= od <= cal["supported_od_range"][1]:
        out["qc_flags"].append("calibration_extrapolation")
    return out

def _import_protocol(rows, src, run_id, mapping, calibration):
    obs, series, events, counts = [],[],[],Counter()
    previous_bottles, previous_mass, unique = {},{},set()
    idx = {s[0]:c for c,s in mapping.items()}
    for n,(row,(stamp,flags)) in enumerate(zip(rows[2:],bounded_timestamps(rows[2:])),3):
        row = list(row)+[None]*max(0,max(mapping)+1-len(row))
        primary = all(parse_number(row[idx[p]])["value"] is not None for p in ("ph","temperature_C","rpm"))
        counts["scheduled_rows"] += 1
        if not primary:
            counts["rows_without_core_measurements"] += 1
            if not any(parse_number(row[idx[p]])["value"] is not None for p in ("ph","temperature_C","rpm","od_fek")):
                continue
        counts["core_observed_rows"] += int(primary)
        record = dict(timestamp=_iso(stamp),local_time=stamp.isoformat() if stamp else None,
            source_row=n,source_id=src["source_id"],source_sheet="Протоколы",
            volume_authoritative_L=10.,volume_basis="user-authoritative operating record",
            availability_time=None,qc_flags=list(flags),primary=primary,
            source_locator=_locator(src,"Протоколы",n),observation_ids={})
        counts["observed_rows_without_time"] += int(stamp is None)
        duplicate = stamp is not None and _iso(stamp) in unique
        if stamp:
            unique.add(_iso(stamp))
        row_obs = []
        for c,spec in mapping.items():
            if _text(row[c]).lower() in EMPTY:
                record[spec[0]] = None
                continue
            o = _observation(run_id,src,"Протоколы",n,c+1,row[c],spec,stamp,flags)
            if duplicate:
                o["qc_flags"].append("duplicate_timestamp")
            obs.append(o)
            row_obs.append(o)
            record[spec[0]] = o["value"] if o["accepted"] else None
            record["observation_ids"][spec[0]] = o["observation_id"]
            counts["spreadsheet_error_cells_observed"] += int("spreadsheet_error" in o["qc_flags"])
            counts["negative_inferred_delivery_cells"] += int("negative_inferred_delivery" in o["qc_flags"])
            if spec[0]=="od_fek" and o["accepted"] and calibration:
                derived = _calibrated(o,calibration)
                obs.append(derived)
                record.update(dry_residue_g_L=derived["value"],
                    dry_residue_ci95=[derived["uncertainty"]["lower"],derived["uncertainty"]["upper"]],
                    calibration_version=calibration["calibration_id"])
                record["observation_ids"]["dry_residue_g_L"] = derived["observation_id"]
                record["qc_flags"].extend(f for f in derived["qc_flags"] if f.startswith("calibration_"))
        gases = [record.get(f"offgas_{p}_pct") for p in ("o2","ch4","co2")]
        gas_sum = sum(gases) if all(v is not None for v in gases) else None
        valid = gas_sum is not None and all(0<=v<=100 for v in gases) and gas_sum<=100.2
        if gas_sum is not None and gas_sum>100.2:
            counts["gas_sum_over_100_2_core_rows"] += int(primary)
            record["qc_flags"].append("invalid_gas_composition_sum")
            for o in row_obs:
                if o["parameter_code"].startswith("offgas_"):
                    o["qc_flags"].append("invalid_gas_composition_sum")
                    o["accepted"] = False
                    o["eligible_as_independent_validation"] = False
                    o["exclusion_reasons"].append("invalid_gas_composition_sum")
        record.update(gas_valid=valid,gas_sum_pct=gas_sum,gas_balance_qualified=False)
        if run_id.endswith("08"):
            for bc,mc,label in ((14,10,"feed"),(23,19,"nh"),(29,25,"koh")):
                bottle = _text(row[bc])
                record[f"{label}_bottle_id"] = bottle or None
                prev = previous_bottles.get(label)
                if bottle and prev and prev[0]!=bottle and stamp:
                    events.append(dict(event_id="evt-"+_id(src["source_id"],n,label),run_id=run_id,
                        kind="bottle_label_change",event_time=_iso(stamp),availability_time=None,
                        description=f"{label}: {prev[0]} -> {bottle}; connection time unresolved within interval",
                        source_locator=_locator(src,"Протоколы",n,bc+1),event_interval=[prev[1],_iso(stamp)],
                        boundary=True,review_state="requires_review"))
                if bottle and stamp:
                    previous_bottles[label] = (bottle,_iso(stamp))
                mass = parse_number(row[mc])["value"]
                old = previous_mass.get(label)
                if old is not None and mass is not None and mass>old and stamp:
                    record["qc_flags"].append(f"{label}_mass_increase_delivery_unresolved")
                    counts["bottle_mass_increases"] += 1
                if mass is not None and stamp:
                    previous_mass[label] = mass
        record["qc_flags"] = sorted(set(record["qc_flags"]))
        series.append(record)
    return obs,series,events,dict(counts)

def _import_events(rows,src,run_id,may=False):
    events = []
    for n,row in enumerate(rows[1:],2):
        if len(row)<5 or not any(_text(x) for x in row[:5]):
            continue
        stamp,flags = parse_timestamp(row[0],row[1])
        category,description = _text(row[3]),_text(row[4])
        action = _text(row[18 if may else 7]) if len(row)>(18 if may else 7) else ""
        text = (category+" "+description+" "+action).lower()
        boundary = any(s in text for s in ("инокуляц","перезас","засев","слив","смыв","замен","останов","технические сбои","датчик"))
        events.append(dict(event_id="evt-"+_id(src["source_id"],"Журнал наблюдений",n),run_id=run_id,
            kind="inoculation_record" if "инокуляц" in category.lower() else "operator_event",
            event_time=_iso(stamp),local_time=stamp.isoformat() if stamp else None,availability_time=None,
            category=category,description=description,action=action,source_locator=_locator(src,"Журнал наблюдений",n),
            qc_flags=flags,boundary=boundary,review_state="requires_review",
            confidence="explicit source category; action interpretation unreviewed"))
    return events

def _import_samples(rows,src,run_id):
    specs = {7:("od_fek","OD","measured","broth","sample OD; instrument label retained"),
        9:("rapid_nh3_nh4_mg_L","mg/L","measured","broth","NH3/NH4 rapid assay; not elemental N"),
        10:("rapid_po4_mg_L","mg/L","measured","broth","PO4 rapid assay; not elemental P"),
        12:("colorimetric_nh3_nh4_mg_L","mg/L","measured","broth","NH3/NH4 colorimetry"),
        13:("colorimetric_po4_mg_L","mg/L","measured","broth","PO4 colorimetry")}
    for c,chemical in {17:"nh4",18:"k",19:"na",20:"mg",21:"ca",22:"cl",23:"no2",24:"so4",25:"no3",26:"hcoo",27:"po4",28:"cu",29:"zn",30:"ni",31:"co",32:"fe",33:"mn"}.items():
        specs[c]=(f"assay_{chemical}_mg_L","mg/L","measured","broth",f"reported {chemical}; method/fraction unverified")
    observations,samples=[],[]
    for n,row in enumerate(rows[2:],3):
        if len(row)<35 or not any(_text(x) for x in row[:4]):
            continue
        stamp,flags=parse_timestamp(row[2],row[3])
        matrix={"КЖ":"broth","ПС":"medium","Вода":"water"}.get(_text(row[0]),"unresolved")
        raw_id=_text(row[1])
        sid=f"{run_id}:{raw_id}" if raw_id else f"{run_id}:unidentified-{n}"
        samples.append(dict(sample_id=sid,raw_sample_id=raw_id,run_id=run_id,matrix=matrix,
            event_time=_iso(stamp),availability_time=None,reported_analysis_date=_text(row[15]) or None,
            source_locator=_locator(src,"Пробы для аналитики",n),instrument_label=_text(row[8]),
            qc_flags=flags+([] if raw_id else ["missing_sample_identity"])))
        for c,spec in specs.items():
            if not _text(row[c]):
                continue
            spec=(*spec[:3],matrix,spec[4])
            o=_observation(run_id,src,"Пробы для аналитики",n,c+1,row[c],spec,stamp,flags,sid)
            o["instrument_label"]=_text(row[8]) if c==7 else None
            if c==7 and _text(row[8]) not in ("ФЭК",""):
                o["qc_flags"].append("instrument_identity_unresolved")
            observations.append(o)
    coverage={s[0]:dict(populated=sum(bool(_text(r[c])) for r in rows[2:] if len(r)>c),
        accepted=sum(o["parameter_code"]==s[0] and o["accepted"] for o in observations),reported_availability=0) for c,s in specs.items()}
    return observations,samples,coverage


def _import_preparations(rows,src,run_id,schema):
    specs={"ПС":(3,14,15,16,9,13,21,35,"medium"),
           "КПС":(2,2,3,18,4,15,22,38,"concentrate"),
           "МЭ":(2,3,4,16,5,14,20,29,"trace_stock")}
    observations,batches,issues=[],[],[]
    if schema=="Титранты":
        definitions=[(2,3,7,[4,5],[6],"koh_titrant"),(10,11,15,[12,13],[14],"ammonia_titrant")]
        hn=2
    else:
        hn,dc,tc,bc,a0,a1,c0,c1,matrix=specs[schema]
        definitions=[(dc,tc,bc,list(range(a0,a1)),list(range(c0,c1)),matrix)]
    for n,row in enumerate(rows[hn:],hn+1):
        for dc,tc,bc,measured,derived,matrix in definitions:
            if len(row)<=bc or not _text(row[bc]):
                continue
            batch_id=_text(row[bc])
            stamp,flags=parse_timestamp(row[dc],row[tc])
            d=parse_local_date(row[dc])
            if d and not date(2026,8,20)<=d<=date(2026,10,1):
                flags.append("preparation_date_outside_run_window")
            if any(f in flags for f in ("invalid_or_incomplete_date","preparation_date_outside_run_window")):
                issues.append(_issue("PREPARATION_DATE_"+batch_id,"high",["nutrient_ledger","batch_linkage"],
                    f"{batch_id} preparation date {row[dc]!r} is unresolved and not repaired.",_locator(src,schema,n,dc+1)))
            batch=dict(batch_id=batch_id,batch_key=f"{run_id}:{schema}:{batch_id}:{n}",run_id=run_id,matrix=matrix,
                preparation_time=_iso(stamp),preparation_local_date=d.isoformat() if d else None,
                raw_preparation_date=_text(row[dc]),raw_preparation_time=_text(row[tc]),connection_time=None,
                availability_time=None,source_locator=_locator(src,schema,n),qc_flags=flags,recipe_observation_ids=[],references=[])
            if schema=="ПС":
                batch["references"]=[_text(row[i]) for i in (17,18,19) if _text(row[i])]
            elif schema=="КПС":
                batch["references"]=[_text(row[15])] if _text(row[15]) else []
            for c in measured+derived:
                if c>=len(row) or not _text(row[c]):
                    continue
                label=" / ".join(_text(rows[h][c]) for h in range(hn) if c<len(rows[h]) and _text(rows[h][c]))
                classification="source-derived" if c in derived else "measured"
                unit="mg/L" if c in derived else "mL" if "мл" in label else "g" if "Навеска" in label or "Масса" in label else "L" if "Объём ПС, л" in label else None
                if schema=="МЭ" and c in measured:
                    unit="g"
                spec=(f"recipe:{schema}:{c+1}",unit,classification,matrix,label or "source recipe field")
                o=_observation(run_id,src,schema,n,c+1,row[c],spec,stamp,flags)
                o["batch_key"]=batch["batch_key"]
                o["eligible_as_independent_validation"]=False
                observations.append(o)
                batch["recipe_observation_ids"].append(o["observation_id"])
            batches.append(batch)
    return observations,batches,issues

def _transfer_audit(rows,src):
    errors,examples=Counter(),[]
    for n,row in enumerate(rows[3:],4):
        for c,v in enumerate(row,1):
            if _text(v).startswith("#"):
                errors[_text(v)]+=1
                if len(examples)<12:
                    examples.append(dict(raw_value=v,source_locator=_locator(src,"Перенос концентраций",n,c)))
    return dict(source_id=src["source_id"],rows=len(rows),columns=max(map(len,rows)),
        role="undated derived worksheet; not a measurement table",event_time=None,
        formula_error_cells=sum(errors.values()),error_counts=dict(errors),error_examples=examples,
        accepted_measurement_count=0,active_batch_reconstruction="dated preparations linked by bottle references; connection times unresolved")

def _segments(run):
    valid=sorted((r for r in run["series"] if r["timestamp"]),key=lambda r:(r["timestamp"],r["source_row"]))
    if not valid:
        run["segments"]=[]
        return
    inoc=[e["event_time"] for e in run["events"] if e["kind"]=="inoculation_record" and e["event_time"]]
    zero=min(inoc or [valid[0]["timestamp"]])
    run["time_zero"]=zero
    run["time_zero_basis"]="first explicit inoculation journal record" if inoc else "first observed process time; inoculation unresolved"
    boundaries=defaultdict(list)
    boundaries[min(zero,valid[0]["timestamp"])]=[]
    for e in run["events"]:
        if e.get("boundary") and e["event_time"] and min(zero,valid[0]["timestamp"])<=e["event_time"]<=valid[-1]["timestamp"]:
            boundaries[e["event_time"]].append(e["event_id"])
    starts=sorted(boundaries)
    segs=[dict(segment_id=f"{run['run_id']}:segment-{i+1:03d}",run_id=run["run_id"],start=t,
               end=starts[i+1] if i+1<len(starts) else None,event_ids=boundaries[t],
               interpretation="conservative interpolation boundary; source interpretation needs review") for i,t in enumerate(starts)]
    zero_dt=datetime.fromisoformat(zero.replace("Z","+00:00"))
    for r in run["series"]:
        r["segment_id"]=segs[max(0,bisect_right(starts,r["timestamp"])-1)]["segment_id"] if r["timestamp"] else None
        r["elapsed_h"]=(datetime.fromisoformat(r["timestamp"].replace("Z","+00:00"))-zero_dt).total_seconds()/3600 if r["timestamp"] else None
    for o in run["observations"]:
        o["segment_id"]=segs[max(0,bisect_right(starts,o["event_time"])-1)]["segment_id"] if o["event_time"] and o["matrix"] in ("broth","gas") else None
    run["segments"]=segs

def _group(observations):
    out=defaultdict(list)
    for o in observations:
        out[o["parameter_code"]].append(o)
    return out

def _finalize(run):
    _segments(run)
    core=[r for r in run["series"] if r["primary"] and r["timestamp"]]
    cov=run["coverage"]
    cov.update(observed_start=min((r["timestamp"] for r in core),default=None),
        observed_end=max((r["timestamp"] for r in core),default=None),
        observed_start_local=min((r["local_time"] for r in core),default=None),
        observed_end_local=max((r["local_time"] for r in core),default=None),
        observations=len(run["observations"]),events=len(run["events"]),segments=len(run["segments"]),
        forecast_available_observations=sum(o["availability_time"] is not None for o in run["observations"]))
    volumes=[r["volume_recorded_L"] for r in core if r.get("volume_recorded_L") is not None]
    cov["recorded_volume_range_L"]=[min(volumes),max(volumes)] if volumes else None
    cov["authoritative_volume_L"]=10.
    cov["parameters"]={p:dict(populated=len(obs),accepted=sum(o["accepted"] for o in obs),
        censored=sum(o["censoring"] is not None for o in obs),classification=sorted({o["classification"] for o in obs}))
        for p,obs in _group(run["observations"]).items()}
    for src in run["sources"]:
        times=[o["event_time"] for o in run["observations"] if o["source_locator"]["source_id"]==src["source_id"] and o["event_time"]]
        src["run_dates"]=[min(times),max(times)] if times else []
    run["issues"].extend([
        _issue("AVAILABILITY_UNKNOWN","blocking",["historical_forecast_qualification"],"Result availability absent. Event-time replay possible; causal rolling-origin validation cannot be claimed.",{"availability_known":cov["forecast_available_observations"]}),
        _issue("GAS_BASIS_AND_EXHAUST","blocking",["measured_gas_uptake","cellular_flux_constraints"],"No verified exhaust flow/tracer imported. Soft-sensor exhaust is a scenario; gas basis/conditions/analyzer delay unresolved."),
        _issue("GAS_COMPOSITION_SUM","high",["gas_balance","gem_constraints"],"O2+CH4+CO2 above 100.2% rejected without renormalization.",{"core_rows":cov.get("gas_sum_over_100_2_core_rows",0)}),
        _issue("NEGATIVE_LEGACY_DELIVERY","high",["nutrient_ledger","productivity"],"Negative bottle differences retained/excluded. Scale noise/reset is not negative delivery.",{"cells":cov.get("negative_inferred_delivery_cells",0)}),
        _issue("VOLUME_RECORD_CONFLICT","high",["inventory_balances"],"User-authoritative 10 L is separate from conflicting raw volumes.",{"raw_range_L":cov["recorded_volume_range_L"],"authoritative_L":10},"decision_recorded_raw_conflict_retained"),
        _issue("TOTAL_DRY_RESIDUE_ENDPOINT","high",["gem_biomass_comparison","calibration_transfer"],"Endpoint is total dry residue. OD-derived residue may include medium solids and is not independent cellular DCW.",resolution="endpoint_decided_transfer_unverified"),
        _issue("LEGACY_DERIVED_NOT_GROUND_TRUTH","high",["evaluation","nutrient_ledger"],"Source ASV/productivity/uptake cannot independently validate calculations sharing parent OD/flow."),
        _issue("D_VERSUS_Q","info",["productivity"],"User confirmed Flow Rate is D h^-1. D*X is a conditional steady-state/nonselective-outflow proxy; transient formation needs inventory and streams.",resolution="resolved_by_user_D_h_inv")])
    if run.get("calibration"):
        run["issues"].append(_issue("CALIBRATION_REPLICATES","high",["uncertainty","forecast_qualification"],
            "Nine dishes have five candidate date/OD groups, not known independent biological replicates.",
            {"dish_count":run["calibration"]["dish_count"],"candidate_groups":run["calibration"]["candidate_replicate_groups"]}))
    seen,duplicates={},0
    for o in run["observations"]:
        if not o["event_time"]:
            continue
        key=(o["event_time"],o["parameter_code"],o["sample_id"],o["source_locator"]["sheet"])
        if key in seen:
            o["qc_flags"].append("duplicate_identity")
            seen[key]["qc_flags"].append("duplicate_identity")
            for duplicate in (o,seen[key]):
                duplicate["accepted"]=False
                duplicate["eligible_as_independent_validation"]=False
                duplicate["exclusion_reasons"].append("duplicate_identity_requires_review")
            duplicates+=1
        else:
            seen[key]=o
    # Acceptance coverage must be computed after duplicate exclusion, not before it.
    for parameter, values in _group(run["observations"]).items():
        cov["parameters"][parameter]["accepted"]=sum(o["accepted"] for o in values)
    cov["duplicate_identity_records"]=duplicates
    cov["pre_inoculation_core_rows"]=sum(r.get("elapsed_h",0)<0 for r in core)
    if cov["pre_inoculation_core_rows"]:
        run["issues"].append(_issue("PRE_INOCULATION_CORE_ROWS","high",["biological_replay"],
            "Core process rows precede the first recorded inoculation; retained as pre-inoculation evidence.",
            {"rows":cov["pre_inoculation_core_rows"]}))
    run["output_status"]=dict(normalized_observations="supported",event_time_replay="supported",
        od_total_dry_residue="conditional",actual_liquid_delivery="blocked",measured_gas_uptake="blocked",
        soft_sensor_exhaust="conditional",cellular_nutrient_uptake="blocked",prospective_forecast_qualification="blocked")
    return run

def _new_run(run_id):
    return {**asdict(Run(run_id)),"schema_version":SCHEMA_VERSION,"parser_version":PARSER_VERSION,
        "observations":[],"events":[],"issues":[],"coverage":{},"sources":[],"series":[],"samples":[],
        "batches":[],"segments":[],"mapping_preview":[],"derived_worksheets":[],
        "decisions":[dict(id="user-reactor-aliases",value="LAB005/FA10/F10/Ф10/YFC-10L share EQ-BR-001"),
                     dict(id="user-timezone",value="Asia/Yekaterinburg UTC+05:00"),
                     dict(id="user-volume",value="10 L authoritative; retain conflicting raw volumes"),
                     dict(id="user-endpoint",value="total dry residue"),
                     dict(id="user-flow-rate",value="Flow Rate is dilution D h^-1, not Q"),
                     dict(id="user-do-basis",value="DO is percent air saturation; calibration conditions unresolved")]}

def import_august(source_dir, *, calibration_path=None, read_time=None):
    """Accept source folder/workspace/protocol path. Eight independent schemas."""
    source_dir=Path(source_dir)
    if source_dir.is_file():
        source_dir=source_dir.parent
    if (source_dir/"02_Experiment_Data").is_dir():
        source_dir=source_dir/"02_Experiment_Data"
    run=_new_run("LAB005-2026-08")
    calibration=read_calibration(calibration_path,read_time) if calibration_path else None
    run["calibration"]=calibration
    if calibration:
        run["sources"].append(calibration["source"])
    schemas={"Протоколы":(2,75),"Журнал наблюдений":(1,8),"Пробы для аналитики":(2,35),
             "ПС":(3,65),"КПС":(2,51),"МЭ":(2,42),"Титранты":(2,16),"Перенос концентраций":(3,227)}
    for name,(hn,width) in schemas.items():
        paths=sorted(source_dir.glob(f"*27.08.2026 - {name}.csv"))
        if not paths:
            run["issues"].append(_issue("MISSING_SOURCE_"+name,"blocking" if name=="Протоколы" else "high",["source_coverage"],f"Missing source schema {name}."))
            continue
        if len(paths)>1:
            raise ValueError(f"Ambiguous {name} source; select immutable snapshot directory")
        rows=_read_csv(paths[0])
        if len(rows)<hn or max(map(len,rows))!=width:
            raise ValueError(f"{name}: expected {width} columns and {hn} headers; mapping review required")
        if name=="Протоколы" and (rows[0][2]!="pH" or rows[0][35]!="CH4, л/час" or "ФЭК" not in rows[0][41]):
            raise ValueError("Protocol schema sentinels changed; mapping review required")
        src=_source(paths[0],{"Протоколы":"process observations and legacy calculations",
            "Журнал наблюдений":"operator event evidence","Пробы для аналитики":"samples and assays",
            "Перенос концентраций":"undated derived worksheet"}.get(name,"preparation records; not connection times"),read_time)
        src.update(header_rows=hn,column_count=width,physical_rows=len(rows),
            formula_error_cells=sum(_text(v).startswith("#") for r in rows[hn:] for v in r))
        run["sources"].append(src)
        if name=="Протоколы":
            obs,series,events,counts=_import_protocol(rows,src,run["run_id"],PROTOCOL_MAP,calibration)
            run["observations"].extend(obs); run["series"].extend(series); run["events"].extend(events)
            run["coverage"].update(counts)
            run["mapping_preview"]=[dict(column=c+1,source_header=" / ".join(_text(rows[h][c]) for h in range(2) if _text(rows[h][c])),
                parameter_code=s[0],unit=s[1],classification=s[2],basis=s[4]) for c,s in PROTOCOL_MAP.items()]
        elif name=="Журнал наблюдений":
            run["events"].extend(_import_events(rows,src,run["run_id"]))
        elif name=="Пробы для аналитики":
            obs,samples,cov=_import_samples(rows,src,run["run_id"])
            run["observations"].extend(obs); run["samples"].extend(samples)
            run["coverage"]["assays"]=cov
        elif name=="Перенос концентраций":
            run["derived_worksheets"].append(_transfer_audit(rows,src))
        else:
            obs,batches,issues=_import_preparations(rows,src,run["run_id"],name)
            run["observations"].extend(obs); run["batches"].extend(batches); run["issues"].extend(issues)
    return _finalize(run)

def import_may(workbook_path, *, calibration_path=None, read_time=None):
    """Separate May process/event replay. Supporting sheets inventoried, not validated."""
    import openpyxl
    wb=openpyxl.load_workbook(workbook_path,data_only=True,read_only=True)
    run=_new_run("LAB005-2026-05")
    src=_source(workbook_path,"May workbook; separate comparison run",read_time)
    src["sheets"]=[dict(name=s.title,rows=s.max_row,columns=s.max_column,
        parser_status="parsed" if s.title in ("Протоколы","Журнал наблюдений") else "inventoried_not_validated") for s in wb]
    run["sources"].append(src)
    calibration=read_calibration(calibration_path,read_time) if calibration_path else None
    run["calibration"]=calibration
    if calibration:
        run["sources"].append(calibration["source"])
    rows=list(wb["Протоколы"].values)
    if len(rows[0])!=58 or rows[0][5]!="pH" or "ФЭК" not in rows[0][38]:
        raise ValueError("May schema changed; mapping review required")
    obs,series,events,counts=_import_protocol(rows,src,run["run_id"],MAY_MAP,calibration)
    run["observations"],run["series"],run["coverage"]=obs,series,counts
    run["events"]=events+_import_events(list(wb["Журнал наблюдений"].values),src,run["run_id"],may=True)
    run["mapping_preview"]=[dict(column=c+1,source_header=_text(rows[0][c]),parameter_code=s[0],unit=s[1],
        classification=s[2],basis=s[4]) for c,s in MAY_MAP.items()]
    wb.close()
    run["issues"].extend([
        _issue("MAY_METHANE_UNIT_CONFLICT","high",["gas_balance"],"Workbook CH4 is L/min; report 1.16 mL/min remains conflicting."),
        _issue("MAY_NH4_UNIT_CONFLICT","high",["nutrient_ledger"],"250 g/L versus 250 mg/L report labels unresolved; English editorial unit is not independent assay."),
        _issue("MAY_SUPPORT_SHEETS_UNVALIDATED","high",["nutrient_ledger","harvest_validation"],"Preparation/separation/drying/drain sheets inventoried; not verified delivery/harvest."),
        _issue("MAY_REPORT_WINDOWS","info",["microscopy_alignment"],"Shift ends 09:00; microscopy extends 15:00. Neither truncates workbook coverage.")])
    return _finalize(run)


def parse_normalized_csv(data, mapping, *, run_id="uploaded", source_name="upload.csv"):
    """Strict upload preview. Offsets/units/bases explicit; no guessed timestamps."""
    required={"event_time","parameter_code","value","unit","classification","basis","matrix"}
    if not required<=mapping.keys():
        raise ValueError(f"Missing mappings: {sorted(required-mapping.keys())}")
    reader=csv.DictReader(io.StringIO(data))
    if not set(mapping.values())<=set(reader.fieldnames or []):
        raise ValueError("Mapping references an absent column")
    src=dict(source_id="src-"+hashlib.sha256(data.encode()).hexdigest()[:20],filename=source_name)
    observations=[]
    for n,row in enumerate(reader,2):
        d={k:row[v] for k,v in mapping.items()}
        if any(d.get(k) is None or not str(d[k]).strip() for k in required - {"value"}):
            raise ValueError(f"Row {n}: required field is empty")
        units={spec[0]:spec[1] for spec in list(PROTOCOL_MAP.values())+list(MAY_MAP.values())}
        units["dry_residue_g_L"]="g/L"
        expected=units.get(d["parameter_code"])
        if d["parameter_code"].endswith("_mg_L"):
            expected="mg/L"
        if expected is not None and d["unit"]!=expected:
            raise ValueError(f"Row {n}: unit for {d['parameter_code']} must be {expected}")
        try:
            event=datetime.fromisoformat(d["event_time"].replace("Z","+00:00"))
            if event.tzinfo is None:
                raise ValueError("event_time requires UTC offset")
            available=datetime.fromisoformat(d["availability_time"].replace("Z","+00:00")) if d.get("availability_time") else None
            if available and (available.tzinfo is None or available<event):
                raise ValueError("availability_time needs offset and cannot precede event_time")
        except (ValueError,TypeError) as exc:
            raise ValueError(f"Row {n}: {exc}") from exc
        allowed={"measured","source-derived","recalculated","imputed","assumed/synthetic","predicted","setpoint"}
        if d["classification"] not in allowed:
            raise ValueError(f"Row {n}: invalid classification")
        if d["classification"] in {"recalculated","imputed","predicted"}:
            raise ValueError(f"Row {n}: {d['classification']} requires full JSON lineage contract")
        spec=(d["parameter_code"],d["unit"],d["classification"],d["matrix"],d["basis"])
        o=_observation(run_id,src,source_name,n,list(reader.fieldnames).index(mapping["value"])+1,d["value"],spec,event,sample_id=d.get("sample_id"))
        o["availability_time"]=_iso(available)
        o["timezone"]=str(event.tzinfo)
        o["equipment_id"]=d.get("equipment_id") or "unresolved"
        o["eligible_for_forecast_input"]=available is not None and o["accepted"] and o["classification"]=="measured"
        observations.append(o)
    return dict(run_id=run_id,schema_version=SCHEMA_VERSION,observations=observations,mapping_preview=mapping,
                rows=len(observations),source_sha256=hashlib.sha256(data.encode()).hexdigest())

def available_at(observations, origin, *, max_age_h=None):
    """Unknown/future availability never passes; event time cannot substitute."""
    cutoff=datetime.fromisoformat(origin.replace("Z","+00:00"))
    if cutoff.tzinfo is None:
        raise ValueError("Forecast origin requires UTC offset")
    out=[]
    for o in observations:
        if not o.get("availability_time") or not o.get("event_time") or not o.get("accepted",False):
            continue
        event=datetime.fromisoformat(o["event_time"].replace("Z","+00:00"))
        available=datetime.fromisoformat(o["availability_time"].replace("Z","+00:00"))
        if event.tzinfo is None or available.tzinfo is None:
            continue
        if event<=available<=cutoff and (max_age_h is None or (cutoff-event).total_seconds()<=max_age_h*3600):
            out.append(o)
    return out
