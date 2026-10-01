"""Small synthetic fixtures; private historical snapshots are never required in CI."""
import csv
import io
from datetime import datetime, time
import pytest
from metabocore.ingestion import (
    parse_number, parse_local_date, parse_local_time, parse_timestamp,
    bounded_timestamps, parse_normalized_csv, available_at, import_august,
    _import_protocol, _import_events, _segments, PROTOCOL_MAP, _calibrated,
)

@pytest.mark.parametrize("raw,expected", [("1,25",1.25),(" 0 ",0.),("−2.5",-2.5),("1e-3",.001)])
def test_decimal_values(raw,expected):
    assert parse_number(raw)["value"] == expected

@pytest.mark.parametrize("raw,flag", [
    ("#DIV/0!","spreadsheet_error"),("#VALUE!","spreadsheet_error"),
    ("ПС113","identifier_in_numeric_cell"),("50-100(10)","unresolved_numeric_annotation"),
    ("","missing"),("-","missing"),("NaN","missing"),("1e999","nonfinite")])
def test_bad_or_missing_never_become_zero(raw,flag):
    assert parse_number(raw)["value"] is None
    assert flag in parse_number(raw)["qc_flags"]

@pytest.mark.parametrize("raw,lo,hi,kind", [
    ("100 - 250",100.,250.,"interval"),("<5",None,5.,"left"),
    (">500",500.,None,"right"),("500+",500.,None,"right"),("≤0.1",None,.1,"left")])
def test_censored_assays_retain_bounds(raw,lo,hi,kind):
    value=parse_number(raw)
    assert (value["value"],value["lower_bound"],value["upper_bound"],value["censoring"]) == (None,lo,hi,kind)

def test_incomplete_invalid_dates_not_repaired():
    assert parse_local_date("21.09") is None
    assert parse_local_date("27.28.26") is None
    assert parse_local_date("20.06.26").isoformat()=="2026-06-20"
    assert parse_timestamp("30.08.26","21:33")[0].isoformat()=="2026-08-30T21:33:00+05:00"

def test_excel_serial_dates_and_subsecond_artifacts():
    assert parse_local_date(46264).year==2026
    value,flags=parse_local_time(time(1,59,59,971000))
    assert value==time(2)
    assert "excel_subsecond_rounding" in flags
    value,flags=parse_local_time(datetime(1900,1,8,17))
    assert value==time(17)
    assert "excel_time_date_artifact" in flags

def test_date_fill_bounded_no_midnight_guess_or_invalid_anchor():
    rows=[["30.08.26","22:00"],["","23:00"],["","00:00"],["31.08.26","01:00"],["bad","02:00"],["","03:00"]]
    values=bounded_timestamps(rows)
    assert values[1][0].day==30
    assert values[2][0] is None
    assert values[3][0].day==31
    assert values[4][0] is values[5][0] is None
    long_rows=[["30.08.26","00:00"]]+[["","01:00"]]*24
    assert bounded_timestamps(long_rows)[-1][0] is None

def protocol_rows():
    h=[""]*75
    h[2]="pH"; h[35]="CH4, л/час"; h[41]="Оптическая (ФЭК)"
    second=[""]*75
    row=[""]*75
    for c,v in {0:"30.08.26",1:"22:00",2:"5,6",3:"42",4:"39",5:"300",6:"9.5",
                13:"-2",14:"ПС0",19:"100",23:"NH0",29:"KOH0",31:"0.2",33:"0.6",
                35:"60",37:"20",38:"81",39:"1",41:"0.427",48:"1.1168",62:"#NUM!",72:"1"}.items():
        row[c]=v
    row2=list(row)
    row2[0]=""; row2[1]="23:00"; row2[14]="ПС1"; row2[19]="120"
    template=[""]*75
    template[1]="23:30"; template[46]="0"; template[62]="#NUM!"
    return [h,second,row,row2,template]

def test_protocol_no_template_coverage_no_gas_renormalization_no_double_ch4():
    src={"source_id":"test"}
    obs,series,events,counts=_import_protocol(protocol_rows(),src,"LAB005-2026-08",PROTOCOL_MAP,None)
    assert counts["scheduled_rows"]==3
    assert counts["core_observed_rows"]==2
    assert len(series)==2
    assert counts["gas_sum_over_100_2_core_rows"]==2
    assert series[0]["gas_sum_pct"]==102
    assert not series[0]["gas_valid"]
    assert series[0]["volume_recorded_L"]==9.5
    assert series[0]["volume_authoritative_L"]==10
    negative=next(o for o in obs if o["parameter_code"]=="legacy_feed_g_h")
    assert negative["value"]==-2 and not negative["accepted"]
    assert "negative_inferred_delivery" in negative["qc_flags"]
    assert next(o for o in obs if o["parameter_code"]=="legacy_ch4_L_min")["classification"]=="source-derived"
    assert next(o for o in obs if o["parameter_code"]=="inlet_ch4_L_h")["classification"]=="measured"
    assert all(o["availability_time"] is None for o in obs)
    assert events[0]["event_interval"]==["2026-08-30T17:00:00Z","2026-08-30T18:00:00Z"]

def test_source_locator_ids_deterministic_and_segments_respect_events():
    rows=protocol_rows()
    first=_import_protocol(rows,{"source_id":"test"},"LAB005-2026-08",PROTOCOL_MAP,None)
    second=_import_protocol(rows,{"source_id":"test"},"LAB005-2026-08",PROTOCOL_MAP,None)
    assert first==second
    assert first[0][0]["source_locator"]["cell"]=="C3"
    run={"run_id":"LAB005-2026-08","observations":first[0],"series":first[1],"events":first[2]}
    run["events"] += _import_events([[""]*8,["30.08.26","21:33","","Инокуляция","засев","","",""]],{"source_id":"journal"},run["run_id"])
    _segments(run)
    assert run["time_zero"]=="2026-08-30T16:33:00Z"
    assert run["series"][0]["elapsed_h"]==.45
    assert run["series"][0]["segment_id"] != run["series"][1]["segment_id"]

def test_full_import_strict_schema_and_provenance(tmp_path):
    path=tmp_path/"Эксперимент_Ф10_27.08.2026 - Протоколы.csv"
    with path.open("w",encoding="utf-8",newline="") as f:
        csv.writer(f).writerows(protocol_rows())
    before=path.read_bytes()
    run=import_august(tmp_path,read_time="2026-10-01T00:00:00Z")
    assert path.read_bytes()==before
    assert run["sources"][0]["sha256"]
    assert run["coverage"]["core_observed_rows"]==2
    assert any(i["issue_id"]=="MISSING_SOURCE_Титранты" for i in run["issues"])
    assert run==import_august(tmp_path,read_time="2026-10-01T00:00:00Z")
    text=path.read_text(encoding="utf-8").replace("CH4, л/час","changed")
    path.write_text(text,encoding="utf-8")
    with pytest.raises(ValueError,match="sentinels"):
        import_august(tmp_path)

def test_od_residue_is_derived_not_gravimetric_and_ci_label_is_limited():
    obs=_import_protocol(protocol_rows(),{"source_id":"test"},"r",PROTOCOL_MAP,None)[0]
    od=next(o for o in obs if o["parameter_code"]=="od_fek")
    cal=dict(coefficient=.22268157726252769,calibration_id="fixture-cal",equation_version="fixture",
             coefficient_ci95=[.20993938306355778,.2354237714614976],rmse_g_L=.6886067,supported_od_range=[8.78,56.57])
    out=_calibrated(od,cal)
    assert out["value"]==pytest.approx(.09508503349109931)
    assert out["classification"]=="recalculated"
    assert out["parent_observation_ids"]==[od["observation_id"]]
    assert not out["eligible_as_independent_validation"]
    assert "calibration_extrapolation" in out["qc_flags"]
    assert out["uncertainty"]["kind"]=="coefficient_only_ci95"

def normalized_csv(availability=""):
    fields=["event_time","parameter_code","value","unit","classification","basis","matrix","availability_time"]
    buf=io.StringIO()
    writer=csv.writer(buf); writer.writerow(fields)
    writer.writerow(["2026-09-01T00:00:00Z","assay_nh4_mg_L","<5","mg/L","measured","NH4","broth",availability])
    return buf.getvalue(),{key:key for key in fields}

def test_upload_availability_missing_not_guessed_from_event():
    text,mapping=normalized_csv()
    out=parse_normalized_csv(text,mapping)
    assert available_at(out["observations"],"2026-09-01T12:00:00Z")==[]
    assert out["observations"][0]["value"] is None

def test_future_assay_excluded_and_stale_data_expires():
    text,mapping=normalized_csv("2026-09-01T08:00:00Z")
    obs=parse_normalized_csv(text,mapping)["observations"]
    assert available_at(obs,"2026-09-01T04:00:00Z")==[]
    assert len(available_at(obs,"2026-09-01T08:00:00Z"))==1
    assert available_at(obs,"2026-09-01T09:00:00Z",max_age_h=4)==[]
    text,_=normalized_csv("2026-08-31T23:00:00Z")
    with pytest.raises(ValueError,match="precede"):
        parse_normalized_csv(text,mapping)

def test_upload_requires_offset_and_full_prediction_lineage():
    text,mapping=normalized_csv()
    with pytest.raises(ValueError,match="offset"):
        parse_normalized_csv(text.replace("2026-09-01T00:00:00Z","2026-09-01T00:00:00"),mapping)
    with pytest.raises(ValueError,match="lineage"):
        parse_normalized_csv(text.replace("measured","predicted"),mapping)

@pytest.mark.parametrize("raw", [">1e999","1e308-1e999"])
def test_nonfinite_censor_bounds_rejected(raw):
    result=parse_number(raw)
    assert result["lower_bound"] is result["upper_bound"] is None
    assert "nonfinite" in result["qc_flags"]

def test_known_upload_units_are_validated():
    text,mapping=normalized_csv()
    with pytest.raises(ValueError,match="unit"):
        parse_normalized_csv(text.replace("mg/L","g/L"),mapping)
