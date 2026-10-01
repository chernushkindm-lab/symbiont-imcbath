"""Synthetic-only tests for the normalized upload -> worker evidence boundary."""
from copy import deepcopy
from datetime import datetime
import csv
import hashlib
import io
import json
from pathlib import Path
import pytest
from metabocore.contracts import Observation, SCHEMA_VERSION
from metabocore.imports import normalise_upload
from metabocore.ingestion import available_at
from metabocore import worker

def observation(identifier, parameter="dry_residue_g_L", value=2., *, event="2026-09-01T00:00:00Z",
                sample=None, row=2, unit="g/L", available=None, accepted=True, segment=None):
    return Observation(
        observation_id=identifier, run_id="synthetic-review", parameter_code=parameter,
        raw_value=str(value), raw_unit=unit, value=value, unit=unit, classification="measured",
        source_locator={"source_id":"synthetic-source","sheet":"synthetic.csv","row":row,"column":3,"cell":f"C{row}"},
        event_time=event, local_time=event, basis="explicit synthetic test fixture",
        matrix="broth", sample_id=sample, availability_time=available,
        accepted=accepted, segment_id=segment,
    ).to_dict()

def imported_run(observations):
    return {"run_id":"synthetic-review","schema_version":SCHEMA_VERSION,
            "observations":observations,"sources":[{"source_id":"synthetic-source","sha256":"a"*64,
            "source_uri":"urn:synthetic-test:source"}],"events":[],"issues":[],
            "qualification":{"forecast":"blocked: synthetic fixture"},
            "mapping_preview":{"test_fixture":True}}

@pytest.fixture
def run_review(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,"PRIVATE",tmp_path)
    folder=tmp_path/"runs"/"synthetic-review"
    folder.mkdir(parents=True)
    saved={}
    def capture(result,target):
        assert target==folder
        saved.clear()
        saved.update(deepcopy(result))
    monkeypatch.setattr(worker,"save_result",capture)
    def run(observations):
        (folder/"result.json").write_text(json.dumps(imported_run(observations)),encoding="utf-8")
        summary=worker.review_import("synthetic-review")
        return summary,deepcopy(saved)
    return run

def upload_fixture(tmp_path, rows):
    folder=tmp_path/"synthetic-import"
    folder.mkdir()
    fields=["timestamp","parameter_code","raw_value","raw_unit","sample_id"]
    text=io.StringIO()
    writer=csv.writer(text); writer.writerow(fields); writer.writerows(rows)
    raw=text.getvalue().encode()
    (folder/"original.csv").write_bytes(raw)
    meta={"filename":"synthetic.csv","sha256":hashlib.sha256(raw).hexdigest(),
          "headers":fields,"delimiter":",","rows":len(rows)+1}
    (folder/"preview.json").write_text(json.dumps(meta),encoding="utf-8")
    request={"run_id":"synthetic-review","classification":"measured","mapping":{k:k for k in fields}}
    return folder,request

def test_upload_excludes_every_member_of_conflicting_duplicate_group(tmp_path):
    folder,request=upload_fixture(tmp_path,[
        ["2026-09-01T00:00:00Z","dry_residue_g_L","2","g/L","A"],
        ["2026-09-01T00:00:00Z","dry_residue_g_L","9","g/L","A"]])
    run=normalise_upload(folder,request)
    assert [o["value"] for o in run["observations"]]==[2.,9.]
    assert all(not o["accepted"] for o in run["observations"])
    assert all("duplicate_identity" in o["qc_flags"] for o in run["observations"])
    assert run["coverage"]["accepted"]==0

def test_upload_sample_identity_prevents_false_duplicate_rejection(tmp_path):
    folder,request=upload_fixture(tmp_path,[
        ["2026-09-01T00:00:00Z","dry_residue_g_L","2","g/L","A"],
        ["2026-09-01T00:00:00Z","dry_residue_g_L","9","g/L","B"]])
    run=normalise_upload(folder,request)
    assert all(o["accepted"] for o in run["observations"])

def test_review_import_retains_unknown_evidence_and_model_gate(run_review):
    obs=[observation("test-1",parameter="unmapped_signal",unit="arbitrary")]
    summary,result=run_review(obs)
    assert summary["model_status"]=="blocked"
    assert result["model_results"]["status"]=="blocked"
    assert result["evaluation"]["status"]=="not_scored"
    assert result["observations"]==obs
    assert result["series"]==[]
    assert result["display_exclusions"][0]["observation_id"]=="test-1"
    assert result["schema_version"]==SCHEMA_VERSION

@pytest.mark.parametrize("parameter",["timestamp","source_row","observation_ids","qc_flags","segment_id"])
def test_untrusted_parameter_cannot_overwrite_chart_metadata(parameter,run_review):
    summary,result=run_review([
        observation("valid",parameter="ph",unit="pH",value=7.1),
        observation("reserved",parameter=parameter,unit="1",value=999,row=3)])
    assert summary["status"]=="completed"
    row=result["series"][0]
    assert datetime.fromisoformat(row["timestamp"]).utcoffset() is not None
    assert row["source_row"]==2
    assert row["observation_ids"]=={"ph":"valid"}
    assert isinstance(row["qc_flags"],list)
    assert len(result["observations"])==2

def test_same_time_independent_samples_preserve_both_values_and_disconnect(run_review):
    summary,result=run_review([observation("A",sample="sample-A",value=2.,row=2),
                               observation("B",sample="sample-B",value=9.,row=3)])
    assert len(result["series"])==2
    assert {r["dry_residue_g_L"] for r in result["series"]}=={2.,9.}
    assert {r["observation_ids"]["dry_residue_g_L"] for r in result["series"]}=={"A","B"}
    assert len({r["segment_id"] for r in result["series"]})==2
    assert all(r["display_kind"]=="point" for r in result["series"])

def test_channel_source_rows_and_unknown_availability_are_not_invented(run_review):
    _,result=run_review([observation("pH",parameter="ph",unit="pH",value=7.1,row=2),
                         observation("DO",parameter="do_pct",unit="%",value=40,row=8)])
    row=result["series"][0]
    assert row["source_row"] is None
    assert row["source_locators"]["ph"]["row"]==2
    assert row["source_locators"]["do_pct"]["row"]==8
    assert row["availability_by_parameter"]=={"ph":None,"do_pct":None}
    assert available_at(result["observations"],"2026-09-01T12:00:00Z")==[]

def test_unsegmented_points_do_not_invent_trace_or_feature_freshness(run_review):
    obs=[observation("early",available="2026-09-01T00:00:00Z"),
         observation("late",event="2026-09-01T02:00:00Z",available="2026-09-01T06:00:00Z",row=3)]
    _,result=run_review(obs)
    assert len({r["segment_id"] for r in result["series"]})==2
    assert available_at(result["observations"],"2026-09-01T03:00:00Z",max_age_h=1)==[]
    assert result["model_results"]["status"]=="blocked"

def test_worker_defensively_excludes_replicates_if_import_flags_are_missing(run_review):
    _,result=run_review([observation("A",sample="same",value=2.,row=2),
                         observation("B",sample="same",value=9.,row=3)])
    row=result["series"][0]
    assert "dry_residue_g_L" not in row
    assert "dry_residue_g_L" not in row["observation_ids"]
    assert any(x["reason"]=="nonunique_chart_parameter_at_sample_time" for x in result["display_exclusions"])

def test_worker_does_not_display_known_channel_with_unqualified_unit(run_review):
    _,result=run_review([observation("wrong-unit",parameter="do_pct",unit="g/L",value=40)])
    assert not result["series"]
    assert result["observations"][0]["raw_unit"]=="g/L"
    assert result["display_exclusions"][0]["reason"]=="chart_unit_mapping_unqualified"

def test_save_result_preserves_evidence_schema_and_versions_result_envelope(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,"chart_exports",lambda result,folder:None)
    monkeypatch.setattr(worker,"git_commit",lambda:"synthetic-test-commit")
    monkeypatch.setattr(worker,"sha",lambda path:"a"*64)
    result=imported_run([observation("one")])
    folder=tmp_path/"synthetic-export"
    worker.save_result(result,folder)
    exported=json.loads((folder/"result.json").read_text(encoding="utf-8"))
    assert exported["schema_version"]==SCHEMA_VERSION
    assert exported["result_schema_version"]==1
    assert exported["observations"][0]["source_locator"]["row"]==2
    assert exported["observations"][0]["availability_time"] is None

def test_normalization_classification_changes_import_fingerprint(run_review):
    measured=observation("same-source-row",parameter="ph",unit="pH",value=7.1)
    _,first=run_review([measured])
    derived=deepcopy(measured)
    derived["classification"]="source-derived"
    _,second=run_review([derived])
    assert first["run_hash"] != second["run_hash"]

def test_uploaded_source_manifest_links_to_verified_original_without_availability_guess(tmp_path):
    folder,request=upload_fixture(tmp_path,[["2026-09-01T00:00:00Z","ph","7.1","pH","A"]])
    run=normalise_upload(folder,request)
    source=run["sources"][0]
    assert source["source_id"]==source["sha256"]==run["observations"][0]["source_locator"]["source_id"]
    assert source["source_uri"]==(folder/"original.csv").resolve().as_uri()
    assert source["parser_version"]=="normalized-upload/1.0.0"
    assert source["read_time"]
    assert source["source_modification_time"] is None
    assert source["availability_time"] is None
    assert run["observations"][0]["availability_time"] is None

def test_changed_original_upload_is_rejected_after_preview(tmp_path):
    folder,request=upload_fixture(tmp_path,[["2026-09-01T00:00:00Z","ph","7.1","pH","A"]])
    with (folder/"original.csv").open("ab") as f:
        f.write(b"tampered")
    with pytest.raises(ValueError,match="checksum"):
        normalise_upload(folder,request)

@pytest.fixture
def snapshot_fixture(tmp_path,monkeypatch):
    source=tmp_path/"synthetic-sources"
    private=tmp_path/"synthetic-private"
    process=source/"02_Experiment_Data"
    calibration=source/"05_Calibration_and_Setpoints"
    process.mkdir(parents=True)
    calibration.mkdir(parents=True)
    protocol=process/"Эксперимент_Ф10_27.08.2026 - Протоколы.csv"
    may=process/"Эксперимент_Ф10_12.05.26.xlsx"
    cal=calibration/"F10_OD_DCW_real_productivity_calibration.xlsx"
    protocol.write_bytes(b"synthetic original protocol bytes")
    may.write_bytes(b"synthetic workbook bytes; never executed")
    cal.write_bytes(b"synthetic calibration bytes; never executed")
    monkeypatch.setattr(worker,"SOURCE",source)
    monkeypatch.setattr(worker,"PRIVATE",private)
    return source,private,protocol,may,cal

def test_snapshot_materialization_never_rereads_changed_live_source(snapshot_fixture,monkeypatch):
    source,private,protocol,_,_=snapshot_fixture
    old=protocol.read_bytes()
    inventory=worker.source_snapshot()
    protocol.write_bytes(b"changed live data")
    original_read=Path.read_bytes
    def no_live_read(path):
        if path.is_relative_to(source):
            raise AssertionError("Live source must not be read after inventory")
        return original_read(path)
    monkeypatch.setattr(Path,"read_bytes",no_live_read)
    inputs=worker.materialize_input_set(inventory,"a"*64)
    archived_input=inputs/protocol.relative_to(source)
    assert archived_input.read_bytes()==old
    assert inputs==private/"input_sets"/("a"*64)
    assert worker.materialize_input_set(inventory,"a"*64)==inputs

def test_live_mutation_during_snapshot_capture_is_detected(snapshot_fixture,monkeypatch):
    _,_,protocol,_,_=snapshot_fixture
    original_read=Path.read_bytes
    def changing_read(path):
        content=original_read(path)
        if path==protocol:
            path.write_bytes(content+b"mutated during read")
        return content
    monkeypatch.setattr(Path,"read_bytes",changing_read)
    with pytest.raises(ValueError,match="changed while snapshotting"):
        worker.source_snapshot()

def test_corrupt_content_addressed_original_cannot_be_materialized(snapshot_fixture):
    _,private,_,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    original=private/inventory[0]["snapshot"]
    original.write_bytes(b"corrupted archive")
    with pytest.raises(ValueError,match="snapshot hash mismatch"):
        worker.materialize_input_set(inventory,"b"*64)
    assert original.read_bytes()==b"corrupted archive"  # rejected, never silently repaired

def test_corrupt_existing_input_set_is_rejected_without_overwrite(snapshot_fixture):
    source,_,protocol,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    inputs=worker.materialize_input_set(inventory,"c"*64)
    target=inputs/protocol.relative_to(source)
    target.write_bytes(b"wrong bytes in parser tree")
    with pytest.raises(ValueError,match="Input-set hash mismatch"):
        worker.materialize_input_set(inventory,"c"*64)
    assert target.read_bytes()==b"wrong bytes in parser tree"

def test_unexpected_parser_tree_file_cannot_be_imported(snapshot_fixture):
    _,_,_,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    inputs=worker.materialize_input_set(inventory,"d"*64)
    (inputs/"02_Experiment_Data"/"unmanifested.csv").write_bytes(b"unmanifested bytes")
    with pytest.raises(ValueError,match="Unexpected files"):
        worker.materialize_input_set(inventory,"d"*64)

def test_snapshot_manifest_cannot_escape_private_input_directory(snapshot_fixture):
    _,_,_,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    forged=deepcopy(inventory)
    forged[0]["relative_path"]="../outside.csv"
    with pytest.raises(ValueError,match="relative path"):
        worker.materialize_input_set(forged,"e"*64)

def test_source_binding_distinguishes_original_snapshot_and_parser_uri(snapshot_fixture):
    from metabocore.ingestion import _source
    source,private,protocol,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    inputs=worker.materialize_input_set(inventory,"f"*64)
    parser_path=inputs/protocol.relative_to(source)
    parsed=_source(parser_path,"synthetic source",read_time="2026-10-02T00:00:00Z")
    result={"sources":[parsed]}
    worker.bind_snapshot_source_metadata(result,inventory,inputs,"f"*64)
    record=next(item for item in inventory if item["filename"]==protocol.name)
    assert parsed["source_uri"]==parsed["original_source_uri"]==protocol.resolve().as_uri()
    assert parsed["parsed_snapshot_uri"]==parser_path.resolve().as_uri()
    assert parsed["immutable_snapshot_uri"]==(private/record["snapshot"]).resolve().as_uri()
    assert parsed["source_modification_time"]==record["local_modified_utc"]
    assert parsed["availability_time"] is None
    assert parsed["sha256"]==record["sha256"]
    assert result["input_set"]["fingerprint"]=="f"*64

def test_post_parse_input_drift_fails_before_model_calculation(snapshot_fixture):
    from metabocore.ingestion import _source
    source,_,protocol,_,_=snapshot_fixture
    inventory=worker.source_snapshot()
    inputs=worker.materialize_input_set(inventory,"1"*64)
    parser_path=inputs/protocol.relative_to(source)
    parsed=_source(parser_path,"synthetic source")
    parser_path.write_bytes(b"changed after parser read")
    with pytest.raises(ValueError,match="drift after materialization"):
        worker.bind_snapshot_source_metadata({"sources":[parsed]},inventory,inputs,"1"*64)

@pytest.mark.parametrize("run_name",["August","May"])
def test_historical_setup_passes_only_verified_snapshot_inputs(snapshot_fixture,monkeypatch,run_name):
    import metabocore.ingestion as ingestion
    source,private,protocol,may,cal=snapshot_fixture
    inventory=worker.source_snapshot()
    original_protocol=protocol.read_bytes()
    original_may=may.read_bytes()
    original_cal=cal.read_bytes()
    protocol.write_bytes(b"new live protocol")
    may.write_bytes(b"new live May workbook")
    cal.write_bytes(b"new live calibration")
    monkeypatch.setattr(worker,"source_snapshot",lambda:inventory)
    monkeypatch.setattr(worker,"historical_fingerprint",lambda originals,run:"2"*64)
    monkeypatch.setattr(worker,"cached_run",lambda run_id,fingerprint:None)
    calls=[]
    def august(folder,*,calibration_path):
        path=folder/protocol.name
        assert path.is_relative_to(private/"input_sets")
        assert path.read_bytes()==original_protocol
        assert calibration_path.read_bytes()==original_cal
        calls.append("August")
        return {"sources":[ingestion._source(path,"synthetic"),ingestion._source(calibration_path,"synthetic")]}
    def may_import(path,*,calibration_path):
        assert path.is_relative_to(private/"input_sets")
        assert path.read_bytes()==original_may
        assert calibration_path.read_bytes()==original_cal
        calls.append("May")
        return {"sources":[ingestion._source(path,"synthetic"),ingestion._source(calibration_path,"synthetic")]}
    monkeypatch.setattr(ingestion,"import_august",august)
    monkeypatch.setattr(ingestion,"import_may",may_import)
    actual_bind=worker.bind_snapshot_source_metadata
    class EndOfImportBoundary(Exception):
        pass
    def stop_before_science(result,originals,input_root,fingerprint):
        actual_bind(result,originals,input_root,fingerprint)
        assert all(s["original_source_uri"].startswith(source.resolve().as_uri()) for s in result["sources"])
        assert all(s["parsed_snapshot_uri"].startswith((private/"input_sets").resolve().as_uri()) for s in result["sources"])
        raise EndOfImportBoundary()
    monkeypatch.setattr(worker,"bind_snapshot_source_metadata",stop_before_science)
    with pytest.raises(EndOfImportBoundary):
        worker.historical(run_name)
    assert calls==[run_name]


def test_export_manifest_retains_input_set_and_report_corruption_blocks_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,"PRIVATE",tmp_path)
    monkeypatch.setattr(worker,"chart_exports",lambda result,folder:None)
    monkeypatch.setattr(worker,"git_commit",lambda:"synthetic-test-commit")
    result=imported_run([observation("synthetic-export-observation")])
    result["run_hash"]="e"*64
    result["input_set"]={"fingerprint":"e"*64,"uri":"urn:synthetic-test:immutable-input-set"}
    folder=tmp_path/"runs"/result["run_id"]
    worker.save_result(result,folder)
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_set"]==result["input_set"]
    assert manifest["exports_sha256"]["report.html"]==hashlib.sha256((folder/"report.html").read_bytes()).hexdigest()
    assert worker.cached_run(result["run_id"],result["run_hash"])["cache"]=="verified_hit"
    with (folder/"report.html").open("a",encoding="utf-8") as stream:
        stream.write("<p>Synthetic corruption check</p>")
    assert worker.cached_run(result["run_id"],result["run_hash"]) is None
