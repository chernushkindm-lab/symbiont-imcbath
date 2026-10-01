"""CSV import adapter sharing the typed historical evidence contract."""
from __future__ import annotations
import csv, hashlib, io, json
from datetime import datetime, timezone
from pathlib import Path
from .contracts import Observation
from .ingestion import parse_number

EXPECTED_UNITS={"ph":{"1","pH"},"temperature_C":{"degC","°C","C"},"rpm":{"rpm","min^-1"},"do_pct":{"%"},"dry_residue_g_L":{"g/L"},"inlet_ch4_L_h":{"L/h"},"dilution_h":{"h^-1","1/h"}}

def normalise_upload(folder:Path, request:dict)->dict:
    meta=json.loads((folder/"preview.json").read_text(encoding="utf-8"))
    original=folder/"original.csv"
    content=original.read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    if digest!=meta["sha256"]:
        raise ValueError("Immutable upload checksum mismatch; preview must be repeated from original bytes")
    # This URI identifies the retained upload artifact, not an invented upstream
    # cloud URL. Filesystem copy/upload time never becomes assay availability.
    meta.update(source_id=digest,source_uri=original.resolve().as_uri(),
                source_uri_role="retained private upload artifact",
                parser_version="normalized-upload/1.0.0",
                role="user-supplied observations; unit/matrix/classification mapping requires review",
                access_status="read",bytes=len(content),read_time=datetime.now(timezone.utc).isoformat(),
                source_modification_time=None,acquisition_time=None,availability_time=None,
                artifact_modification_time=datetime.fromtimestamp(original.stat().st_mtime,timezone.utc).isoformat())
    rows=list(csv.DictReader(io.StringIO(content.decode("utf-8-sig")),delimiter=meta["delimiter"]))
    mapping=request["mapping"]
    required=("timestamp","parameter_code","raw_value","raw_unit")
    if any(k not in mapping for k in required): raise ValueError("Map timestamp, parameter_code, raw_value and raw_unit")
    if any(v not in meta["headers"] for v in mapping.values()): raise ValueError("Mapping references an unknown column")
    result=[];issues=[];seen={}
    for rowno,row in enumerate(rows,2):
        original_time=row.get(mapping["timestamp"],"").strip()
        flags=[];reasons=[]
        try:
            dt=datetime.fromisoformat(original_time.replace("Z","+00:00"))
            if dt.tzinfo is None: raise ValueError()
            timestamp=dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            timestamp=None;flags.append("invalid_or_ambiguous_timestamp");reasons.append("event_time_missing")
        raw=row.get(mapping["raw_value"],"")
        parsed=parse_number(raw);flags+=parsed["qc_flags"]
        if parsed["value"] is None and parsed["censoring"] is None: reasons.append("invalid_or_missing_value")
        available=row.get(mapping.get("availability_timestamp",""),"").strip() or None
        if available:
            try:
                a=datetime.fromisoformat(available.replace("Z","+00:00"))
                if a.tzinfo is None:raise ValueError()
                available=a.astimezone(timezone.utc).isoformat()
                if timestamp and a < dt:flags.append("availability_precedes_event");reasons.append("availability_precedes_event")
            except ValueError:available=None;flags.append("invalid_availability_timestamp")
        if available is None:flags.append("availability_unknown")
        unit=row.get(mapping["raw_unit"],"").strip()
        code=row.get(mapping["parameter_code"],"").strip()
        sample=row.get(mapping.get("sample_id","")) or None
        if not unit:flags.append("unit_missing");reasons.append("unit_missing")
        elif code in EXPECTED_UNITS and unit not in EXPECTED_UNITS[code]:flags.append("unit_mismatch");reasons.append("unit_mismatch")
        elif code not in EXPECTED_UNITS:flags.append("unit_basis_requires_review")
        if not code:flags.append("parameter_missing");reasons.append("parameter_missing")
        key=(timestamp,code,sample)
        obs=Observation(observation_id=f'{meta["sha256"][:12]}:{rowno}',run_id=request["run_id"],parameter_code=code,raw_value=raw,raw_unit=unit,value=parsed["value"],unit=unit,classification=request["classification"],source_locator={"source_id":meta["sha256"],"sheet":meta["filename"],"row":rowno},event_time=timestamp,local_time=original_time or None,basis="As supplied; no implicit unit conversion",matrix="unspecified",sample_id=sample,equipment_id="unassigned",availability_time=available,timezone="explicit ISO offset",qc_flags=flags,accepted=not reasons,exclusion_reasons=reasons,lower_bound=parsed["lower_bound"],upper_bound=parsed["upper_bound"],censoring=parsed["censoring"]).to_dict()
        result.append(obs)
        seen.setdefault(key,[]).append(obs)
        if flags:issues.append({"severity":"warning","code":"import_qc","row":rowno,"details":flags})
    # Reject every member of an unresolved duplicate identity group. First-row
    # preference would silently choose a value when duplicates conflict.
    for duplicates in seen.values():
        if len(duplicates)<2:
            continue
        for obs in duplicates:
            obs["qc_flags"]=sorted(set(obs["qc_flags"]+["duplicate_identity"]))
            obs["exclusion_reasons"]=sorted(set(obs["exclusion_reasons"]+["duplicate_identity_requires_review"]))
            obs["accepted"]=False
        issues.append({"severity":"warning","code":"duplicate_identity_requires_review",
                       "rows":[o["source_locator"]["row"] for o in duplicates],
                       "observation_ids":[o["observation_id"] for o in duplicates]})
    return {"run_id":request["run_id"],"observations":result,"series":[],"events":[],"issues":issues,"sources":[meta],"coverage":{"record_count":len(result),"accepted":sum(o["accepted"] for o in result)},"qualification":{"historical":"Imported evidence; review units, classifications, matrix and mapping","forecast":"blocked: availability and model inputs require qualification"},"mapping_preview":mapping}
