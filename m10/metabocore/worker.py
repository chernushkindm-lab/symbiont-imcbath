"""Deterministic historical worker and provenance-preserving private exports."""
from __future__ import annotations
import argparse, csv, hashlib, html, importlib.metadata, json, math, os, platform, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PRIVATE=Path(os.getenv("M10_DATA_DIR",str(ROOT/"m10/private"))).resolve()
SOURCE=Path(os.getenv("M10_SOURCE_DIR",str(ROOT.parent))).resolve()
VERSION="m10-historical-0.2.0"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(value):
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,(datetime,Path)): return str(value)
    if hasattr(value,"item"): return clean(value.item())
    return value
def write_json(path,value):
    path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
def timestamp(row): return row.get("timestamp") or row.get("event_time") or row.get("event_timestamp")
def as_dt(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def git_commit():
    try:return subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,timeout=10).strip()
    except Exception:return "unavailable"
def source_snapshot():
    """Capture exact bytes once; never hash live bytes and then copy another version."""
    inventory=[]
    for folder in ["01_Laboratory_and_Equipment","02_Experiment_Data","03_Experiment_and_Shift_Reports","04_Protocols_and_Methods","05_Calibration_and_Setpoints","07_Microbiology_and_Microscopy"]:
        if not (SOURCE/folder).exists():
            continue
        for path in sorted((SOURCE/folder).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in (".csv",".xlsx",".docx",".ipynb",".py",".pdf",".tif"):
                continue
            relative=path.relative_to(SOURCE).as_posix()
            source_uri=path.resolve().as_uri()
            try:
                before=path.stat()
                content=path.read_bytes()
                after=path.stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(content)!=after.st_size:
                    raise ValueError(f"Source changed while snapshotting: {relative}; retry from a stable version")
            except OSError as error:
                inventory.append({"filename":path.name,"relative_path":relative,"source_uri":source_uri,
                    "sha256":None,"access_status":"local_read_failed","error":str(error)})
                continue
            digest=hashlib.sha256(content).hexdigest()
            destination=_contained_relative(PRIVATE,f"originals/{digest}/{path.name}")
            destination.parent.mkdir(parents=True,exist_ok=True)
            try:
                with destination.open("xb") as stream:
                    stream.write(content)
            except FileExistsError:
                pass
            if sha(destination)!=digest:
                raise ValueError(f"Immutable source snapshot hash mismatch: {relative}")
            inventory.append({"filename":path.name,"relative_path":relative,"source_uri":source_uri,
                "source_uri_role":"original mounted source reference","sha256":digest,"bytes":len(content),
                "local_modified_utc":datetime.fromtimestamp(before.st_mtime,timezone.utc).isoformat(),
                "read_at":datetime.now(timezone.utc).isoformat(),
                "snapshot":destination.relative_to(PRIVATE).as_posix(),
                "snapshot_uri":destination.resolve().as_uri(),
                "snapshot_role":"content-addressed immutable acquisition bytes",
                "access_status":"local_bytes_read"})
    return inventory


def _contained_relative(root, relative):
    """Resolve manifest paths only inside the named private/workspace directory."""
    from pathlib import PurePosixPath
    text=str(relative).replace("\\","/")
    parts=PurePosixPath(text)
    if not text or parts.is_absolute() or ".." in parts.parts or ":" in text:
        raise ValueError("Invalid relative path in snapshot manifest")
    root=root.resolve()
    target=(root/Path(*parts.parts)).resolve()
    if not target.is_relative_to(root) or target==root:
        raise ValueError("Snapshot manifest path escapes its intended directory")
    return target


def materialize_input_set(originals, fingerprint):
    """Create a hash-verified parser tree from archived bytes, never from SOURCE.

    Existing inconsistent bytes or unexpected files are an error. No original or
    prior input set is silently repaired, deleted, or overwritten.
    """
    import re
    if not re.fullmatch(r"[0-9a-f]{64}",fingerprint):
        raise ValueError("Invalid input-set fingerprint")
    root=_contained_relative(PRIVATE,f"input_sets/{fingerprint}")
    root.mkdir(parents=True,exist_ok=True)
    entries=[]
    expected=set()
    for item in originals:
        if item.get("access_status")!="local_bytes_read":
            continue
        digest=item.get("sha256")
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
            raise ValueError("Invalid snapshot checksum in manifest")
        original=_contained_relative(PRIVATE,item["snapshot"])
        destination=_contained_relative(root,item["relative_path"])
        relative=destination.relative_to(root).as_posix()
        if relative in expected:
            raise ValueError(f"Duplicate relative path in snapshot manifest: {relative}")
        expected.add(relative)
        content=original.read_bytes()
        if hashlib.sha256(content).hexdigest()!=digest:
            raise ValueError(f"Immutable source snapshot hash mismatch: {relative}")
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            with destination.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            pass
        if sha(destination)!=digest:
            raise ValueError(f"Input-set hash mismatch: {relative}")
        entries.append({"relative_path":relative,"sha256":digest,
            "original_source_uri":item.get("source_uri"),
            "immutable_snapshot_uri":original.as_uri(),"parsed_snapshot_uri":destination.as_uri()})
    manifest_path=root/"input-manifest.json"
    actual={path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual-expected-{"input-manifest.json"}:
        raise ValueError("Unexpected files in immutable input set")
    manifest={"schema_version":1,"fingerprint":fingerprint,"inputs":sorted(entries,key=lambda item:item["relative_path"])}
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8"))!=manifest:
            raise ValueError("Input-set manifest differs from requested snapshot")
    else:
        with manifest_path.open("x",encoding="utf-8") as stream:
            json.dump(manifest,stream,ensure_ascii=False,indent=2)
    return root


def bind_snapshot_source_metadata(result, originals, input_root, fingerprint):
    """Verify parser-reported hashes and distinguish source references from copies."""
    lookup={}
    for item in originals:
        if item.get("access_status")!="local_bytes_read":
            continue
        path=_contained_relative(input_root,item["relative_path"])
        lookup[path.as_uri()]=(item,path)
    for source in result.get("sources",[]):
        parsed_uri=source.get("source_uri")
        if parsed_uri not in lookup:
            raise ValueError("Parser source is outside the verified historical input set")
        item,path=lookup[parsed_uri]
        if source.get("sha256")!=item["sha256"] or sha(path)!=item["sha256"]:
            raise ValueError(f"Historical input drift after materialization: {item['relative_path']}")
        source["original_source_uri"]=item.get("source_uri")
        source["parsed_snapshot_uri"]=parsed_uri
        source["immutable_snapshot_uri"]=_contained_relative(PRIVATE,item["snapshot"]).as_uri()
        source["source_uri"]=item.get("source_uri") or source["immutable_snapshot_uri"]
        source["source_uri_role"]="original source reference; exact parsed bytes identified by immutable snapshot and SHA-256"
        source["snapshot_modification_time"]=source.get("source_modification_time")
        source["source_modification_time"]=item.get("local_modified_utc")
        source["snapshot_acquired_at"]=item.get("read_at")
        source["input_set_fingerprint"]=fingerprint
    result["input_set"]={"fingerprint":fingerprint,"uri":input_root.as_uri(),
        "manifest_uri":(input_root/"input-manifest.json").as_uri(),
        "policy":"parser reads verified private snapshots only; original source references are metadata"}

def chart_exports(result,folder):
    rows=result.get("series",[])
    points=[]
    for r in rows:
        t=timestamp(r);v=r.get("dry_residue_g_L")
        if t and isinstance(v,(int,float)) and math.isfinite(v):points.append((as_dt(t).timestamp(),v,r.get("segment_id")))
    w,h=1200,440; left,top,pw,ph=80,72,1080,300
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#f4f8f9"/><g font-family="Arial" fill="#293d45"><text x="50" y="35" font-size="22">SYMBIONT / {html.escape(result["run_id"])}</text><text x="50" y="60" font-size="13">Reconstruction · OD-derived total dry residue · g/L · no independent cellular DCW claim</text>']
    try:
        from PIL import Image,ImageDraw
        im=Image.new("RGB",(w,h),"#f4f8f9");draw=ImageDraw.Draw(im)
        draw.text((50,25),f"SYMBIONT / {result['run_id']}",fill="#293d45")
        draw.text((50,47),"OD-derived total dry residue (g/L); observation-window reconstruction",fill="#617f8d")
    except ImportError: im=draw=None
    if points:
        mn=min(p[0] for p in points);mx=max(p[0] for p in points); ytop=max(p[1] for p in points)*1.12 or 1
        def xy(p):return left+(p[0]-mn)/max(mx-mn,1)*pw,top+ph-p[1]/ytop*ph
        for n in range(5):
            y=top+n*ph/4
            svg.append(f'<path d="M{left} {y}H{left+pw}" stroke="#dce7eb"/><text x="20" y="{y+4}" font-size="12">{ytop*(4-n)/4:.2f}</text>')
            if draw:draw.line((left,y,left+pw,y),fill="#dce7eb");draw.text((20,y),f"{ytop*(4-n)/4:.2f}",fill="#617f8d")
        prior=None
        for p in points:
            x,y=xy(p)
            if prior and p[0]-prior[0]<=4*3600 and prior[2]==p[2]:
                a,b=xy(prior);svg.append(f'<path d="M{a:.2f} {b:.2f}L{x:.2f} {y:.2f}" fill="none" stroke="#48818e" stroke-width="1.4"/>')
                if draw:draw.line((a,b,x,y),fill="#48818e",width=2)
            svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="#48818e"/>')
            if draw:draw.ellipse((x-2,y-2,x+2,y+2),fill="#48818e")
            prior=p
        svg.append(f'<text x="{left}" y="409" font-size="12">{html.escape(as_dt(rows[0]["timestamp"]).isoformat() if rows and rows[0].get("timestamp") else "")}</text>')
    else:svg.append('<text x="80" y="220" font-size="18">No accepted time-linked dry-residue observations</text>')
    svg.append('</g></svg>');(folder/"chart.svg").write_text("".join(svg),encoding="utf-8")
    if im:im.save(folder/"chart.png")

def save_result(result,folder):
    folder.mkdir(parents=True,exist_ok=True)
    result=clean(result)
    result.setdefault("created_at",datetime.now(timezone.utc).isoformat())
    result.setdefault("schema_version","m10.evidence/1.0")
    result["result_schema_version"]=1
    observations=result.get("observations",[])
    result["observation_count"]=len(observations)
    assay_codes={"rapid_nh3_nh4_mg_L","rapid_po4_mg_L","assay_cu_mg_L","assay_fe_mg_L","assay_zn_mg_L","assay_mn_mg_L"}
    result["assay_points"]=[{k:o.get(k) for k in ("observation_id","parameter_code","event_time","local_time","value","lower_bound","upper_bound","censoring","raw_value","unit","basis","matrix","sample_id","source_locator","qc_flags","availability_time")} for o in observations if o.get("accepted") and o.get("event_time") and o.get("matrix")=="broth" and o.get("parameter_code") in assay_codes]

    keys=sorted({k for r in observations for k in r})
    # JSON in compound CSV cells retains censoring, QC and lineage without loss.
    with (folder/"observations.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for r in observations:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    try:
        import pyarrow as pa, pyarrow.parquet as pq
        # Stable scalar columns plus full record JSON preserve heterogeneous evidence.
        records=[{"observation_id":str(r.get("observation_id",r.get("id",""))),"run_id":result["run_id"],"parameter_code":str(r.get("parameter_code","")),"record_json":json.dumps(r,ensure_ascii=False)} for r in observations]
        table=pa.Table.from_pylist(records) if records else pa.table({"observation_id":pa.array([],type=pa.string()),"run_id":pa.array([],type=pa.string()),"parameter_code":pa.array([],type=pa.string()),"record_json":pa.array([],type=pa.string())})
        pq.write_table(table,folder/"observations.parquet")
    except ImportError:result.setdefault("export_limitations",[]).append("pyarrow unavailable")
    evaluation=result.get("evaluation",{})
    paired=evaluation.get("paired",[]) if isinstance(evaluation,dict) else []
    with (folder/"evaluation.csv").open("w",newline="",encoding="utf-8-sig") as f:
        cols=sorted({k for r in paired for k in r}) or ["run_id","status","reason"]
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        if paired:
            for r in paired:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
        else:writer.writerow({"run_id":result["run_id"],"status":"not_scored","reason":"No qualified paired forecasts; missing information-availability and comparable target evidence"})
    chart_exports(result,folder)
    manifest={"schema_version":1,"worker_version":VERSION,"source_commit":git_commit(),"python":platform.python_version(),"model_sha256":sha(ROOT/"ModelFiles/json/iMcBath.json"),"decisions_sha256":sha(ROOT/"m10/config/decisions.json"),"sources":result.get("sources",[]),"immutable_originals":result.get("immutable_originals",[]),"input_set":result.get("input_set"),"run_hash":result.get("run_hash"),"classification":"private historical evidence; conditional model scenarios separate","software":{}}
    for package in ("cobra","scipy","numpy","pandas","fastapi","pyarrow"):
        try:manifest["software"][package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    manifest["code_hashes"]={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/"m10/metabocore").glob("*.py"))}
    write_json(folder/"result.json",result)
    manifest["exports_sha256"]={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name not in ("manifest.json","report.html")}
    esc=lambda x:html.escape(json.dumps(x,ensure_ascii=False,indent=2,default=str))
    report='<!doctype html><html><meta charset="utf-8"><title>SYMBIONT historical report</title><style>body{font:16px/1.5 system-ui;background:#f4f8f9;color:#293d45;max-width:1100px;margin:50px auto;padding:20px}h1{font-weight:400}pre{white-space:pre-wrap;border:1px solid #d3e1e7;padding:20px;font-size:13px}img{width:100%}</style><h1>SYMBIONT / '+html.escape(result["run_id"])+'</h1><p>Observation-window reconstruction. Total dry residue is the user-selected endpoint. Conditional model capacity is not an independently validated culture forecast.</p>'
    report+='<h2>Qualification</h2><pre>'+esc(result.get("qualification"))+'</pre><h2>Coverage</h2><pre>'+esc(result.get("coverage"))+'</pre><h2>Model result</h2><pre>'+esc(result.get("model_results",{}))+'</pre><h2>Unresolved issues</h2><pre>'+esc(result.get("issues",[]))+'</pre><h2>Reproducibility</h2><pre>'+esc(manifest)+'</pre></html>'
    (folder/"report.html").write_text(report,encoding="utf-8")
    manifest["exports_sha256"]["report.html"]=sha(folder/"report.html")
    write_json(folder/"manifest.json",manifest)

def historical_fingerprint(originals,run_name):
    paths=list((ROOT/"m10/metabocore").glob("*.py"))+list((ROOT/"src/symbiont_imcbath").glob("*.py"))
    paths += [ROOT/"m10/config/decisions.json",ROOT/"m10/requirements-lock.txt",ROOT/"profiles/symbiont-reference.json",ROOT/"ModelFiles/json/iMcBath.json"]
    audit=ROOT/"reports/m10-audit/run-metadata.json"
    if audit.exists():paths.append(audit)
    return hashlib.sha256(json.dumps({"source_commit":git_commit(),"source_bytes":[(x["relative_path"],x.get("sha256"),x["access_status"]) for x in originals],"run":run_name,"version":VERSION,"artifacts":{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.exists()}},sort_keys=True).encode()).hexdigest()

def cached_run(run_id,fingerprint):
    folder=PRIVATE/"runs"/run_id
    try:
        manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("run_hash")!=fingerprint:return None
        if any(not (folder/name).is_file() or sha(folder/name)!=digest for name,digest in manifest["exports_sha256"].items()):return None
        result=json.loads((folder/"result.json").read_text(encoding="utf-8"))
        return {"run_id":run_id,"run_hash":fingerprint,"observations":len(result.get("observations",[])),"status":"completed","cache":"verified_hit","qualification":result.get("qualification")}
    except (OSError,ValueError,KeyError):return None

def historical(run_name):
    from .ingestion import import_august,import_may
    originals=source_snapshot()
    fingerprint=historical_fingerprint(originals,run_name)
    cached=cached_run("LAB005-2026-08" if run_name=="August" else "LAB005-2026-05",fingerprint)
    if cached:return cached
    input_root=materialize_input_set(originals,fingerprint)
    if run_name=="August":
        result=import_august(input_root/"02_Experiment_Data",calibration_path=input_root/"05_Calibration_and_Setpoints/F10_OD_DCW_real_productivity_calibration.xlsx")
    else:result=import_may(input_root/"02_Experiment_Data/Эксперимент_Ф10_12.05.26.xlsx",calibration_path=input_root/"05_Calibration_and_Setpoints/F10_OD_DCW_real_productivity_calibration.xlsx")
    bind_snapshot_source_metadata(result,originals,input_root,fingerprint)
    metadata_path=PRIVATE/"drive_sources.json"
    if metadata_path.exists():
        remote=json.loads(metadata_path.read_text(encoding="utf-8"))
        remote += [{"id":"1M0SyF9P9GPtAiC5aMzUxjmy4VpAOMm5L","filename":"F10_OD_DCW_real_productivity_calibration.xlsx","url":"https://docs.google.com/spreadsheets/d/1M0SyF9P9GPtAiC5aMzUxjmy4VpAOMm5L/edit","modified":"2026-09-27T08:39:06.272Z"}]
        by_name={x["filename"]:x for x in remote}
        for source in result.get("sources",[]):
            name=source.get("filename",source.get("file_name",Path(source.get("path","")).name))
            if name in by_name:
                source["drive_reference"]=by_name[name]
                source["remote_byte_identity"]="not independently downloaded; local mounted snapshot is hashed"
    result["immutable_originals"]=originals
    from .historical_analysis import analyze_observations
    cal=result.get("calibration") or {}
    ci={cal["calibration_id"]:{"coefficient":cal["coefficient"],"coefficient_interval":cal["coefficient_ci95"],"source":cal["ci_locators"]}} if cal else {}
    result["historical_analysis"]=analyze_observations(result.get("observations",[]),calibration_intervals=ci)
    proxy_by_time={x["event_time"]:x["dilution_residue_proxy_g_l_h"] for x in result["historical_analysis"]["dilution_productivity_proxies"]}
    for row in result.get("series",[]): row["dilution_residue_proxy_g_L_h"]=proxy_by_time.get(row.get("timestamp"))
    result["qualification"]={"code":"See validation report for test result","historical":"Imported and QC reviewed; dry-residue proxy is calibration-dependent","gas_uptake":"blocked as measured result: no validated exhaust/tracer and gas-basis conflicts","GEM":"conditional capacity only; Bath is a surrogate for VS1","kinetic":"mechanistic implementation tested on reference cases; not calibrated to LAB005","forecast":"unqualified: unknown reporting times, transfer inputs and endpoint bridge","deployment":"local authenticated service; access checks required"}
    rows=result.get("series",[])
    candidates=[r for r in rows if isinstance(r.get("dry_residue_g_L"),(float,int)) and r["dry_residue_g_L"]>0 and r.get("gas_valid") and isinstance(r.get("od_fek"),(float,int)) and 8.78<=r["od_fek"]<=56.57 and all(isinstance(r.get(k),(float,int)) and math.isfinite(r[k]) and r[k]>0 for k in ("inlet_ch4_L_h","inlet_o2_L_min","o2_purity_pct")) and r["o2_purity_pct"]<=100 and (r.get("inlet_air_L_min") is None or r["inlet_air_L_min"]>=0)]
    result["model_results"]={"historical_reconciliation":{"status":"blocked","reason":"Exhaust is unmeasured; uptake is not identifiable from inlet data alone"}}
    try:
        from .gem import capacity,model_audit_summary,reference_regression
        audit=model_audit_summary();write_json(PRIVATE/"model-audit.json",audit)
        result["model_results"]["model_regression"]=reference_regression()
        if candidates and run_name=="August":
            row=candidates[0]; biomass=row["dry_residue_g_L"]
            # Inlet supply scenario. Only the missing-air interpretation is user-confirmed.
            molar_volume=24.465
            air=row["inlet_air_L_min"] if row.get("inlet_air_L_min") is not None else 0.0
            oxygen=row["inlet_o2_L_min"];purity=row["o2_purity_pct"]/100
            methane=row["inlet_ch4_L_h"]/molar_volume*1000/(10*biomass)
            o2=(air*.2095+oxygen*purity)*60/molar_volume*1000/(10*biomass)
            locator=f'{result["run_id"]} protocol row {row.get("source_row","unknown")}'
            row_ids=row.get("observation_ids",{})
            def parent_ids(codes):
                if isinstance(row_ids,dict): return [row_ids[c] for c in codes if c in row_ids]
                return [o["observation_id"] for o in result["observations"] if o.get("event_time")==row["timestamp"] and o.get("source_locator",{}).get("row")==row["source_row"] and o.get("parameter_code") in codes]
            assumption="Assumed dry inlet volume at 25 C/1 atm, pure methane, 100% supply availability, model/residue=1. Reported oxygen purity used. No transfer or uptake inferred."
            bounds={
              "EX_ch4_e":{"lower":0.0,"upper":methane,"unit":"mmol/(g_model_biomass h)","provenance":"assumed","source":locator+"; "+assumption,"parent_observation_ids":parent_ids(["inlet_ch4_L_h","dry_residue_g_L"])},
              "EX_o2_e":{"lower":0.0,"upper":o2,"unit":"mmol/(g_model_biomass h)","provenance":"assumed","source":locator+"; "+assumption+" Blank air with recorded concentrator means air off per user decision 2026-10-02.1.","parent_observation_ids":parent_ids(["inlet_air_L_min","inlet_o2_L_min","o2_purity_pct","dry_residue_g_L"])},
              "EX_nh4_e":{"lower":0.0,"upper":2.3,"unit":"mmol/(g_model_biomass h)","provenance":"assumed","source":"Existing symbiont-reference NH4 cap 2.3; not a measured LAB005 supply or uptake","parent_observation_ids":[]}
            }
            request={"schema_version":1,"run_id":result["run_id"],"window_id":str(timestamp(row)),"mode":"capacity","scenario_id":"symbiont-reference","uptake_bounds":bounds,"biomass":{"value":biomass,"unit":"g_dry_residue/L","source":locator},"biomass_mapping":{"factor_g_model_per_g_residue":1.0,"source":"Illustrative assumption, not a measured cellular/producer mapping","status":"assumed"},"fva_reactions":["EX_co2_e"],"sensitivity_fraction":0.05}
            result["model_results"]["conditional_window"]={"request":request,"result":capacity(request),"classification":"conditional scenario at observed state; not forecast or measured uptake","numerical_gas_triplet_only":True,"gas_calibration_basis_validated":False,"observed_row":row}
        else:
            reason="May methane L/min channel has unresolved report unit conflict; no historical flux constraint is qualified" if run_name=="May" else "No numerically accepted triplet with recorded concentrator flow/purity and OD within calibration range"
            result["model_results"]["conditional_window"]={"status":"blocked","reason":reason}
    except Exception as error:result["model_results"]["GEM_error"]={"status":"failed","error":str(error)}
    result["evaluation"]={"paired":[],"status":"not_scored","reason":"No independently qualified historical GEM/kinetic forecasts. Missing assay availability cannot be treated as available at measurement time."}
    from .evaluation import rolling_origin_baselines
    records=[]
    for o in result.get("observations",[]):
        code=str(o.get("parameter_code",""))
        value=o.get("normalized_value",o.get("value"))
        if ("residue" in code.lower() or "biomass" in code.lower()) and isinstance(value,(float,int)):
            records.append({"timestamp":o.get("event_time",o.get("event_timestamp")),"available_at":o.get("availability_time",o.get("availability_timestamp")),"value":value,"run_id":result["run_id"],"segment_id":o.get("segment_id"),"evidence_id":o.get("observation_id"),"classification":o.get("classification"),"independent_assay":False})
    try:result["evaluation"]["baseline"]=rolling_origin_baselines(records)
    except Exception as e:result["evaluation"]["baseline"]={"status":"blocked","reason":str(e)}
    result["run_hash"]=fingerprint
    from .historical_analysis import build_hypotheses
    result["hypotheses"]=build_hypotheses(result)
    save_result(result,PRIVATE/"runs"/result["run_id"])
    return {"run_id":result["run_id"],"run_hash":result["run_hash"],"observations":len(result.get("observations",[])),"status":"completed","qualification":result["qualification"]}

def review_import(run_id):
    """Prepare imported observations for display without choosing replicate values.

    Unknown parameters remain in the evidence/export records. Only explicit
    numerical channels can become chart fields; they cannot overwrite metadata.
    Independent samples and unsegmented points receive distinct display segments.
    """
    import re
    from .ingestion import PROTOCOL_MAP, MAY_MAP
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",run_id):
        raise ValueError("Invalid run ID")
    folder=PRIVATE/"runs"/run_id
    result=json.loads((folder/"result.json").read_text(encoding="utf-8"))
    display_units={spec[0]:spec[1] for spec in list(PROTOCOL_MAP.values())+list(MAY_MAP.values())}
    display_units.update({"dry_residue_g_L":"g/L","dilution_h":"1/h",
        "rapid_nh3_nh4_mg_L":"mg/L","rapid_po4_mg_L":"mg/L",
        "colorimetric_nh3_nh4_mg_L":"mg/L","colorimetric_po4_mg_L":"mg/L"})
    for chemical in ("nh4","k","na","mg","ca","cl","no2","so4","no3","hcoo","po4","cu","zn","ni","co","fe","mn"):
        display_units[f"assay_{chemical}_mg_L"]="mg/L"
    unit_aliases={"pH":{"pH","1"},"degC":{"degC","C","°C"},"rpm":{"rpm","min^-1"},"1/h":{"1/h","h^-1"}}
    by_identity={}
    display_exclusions=[]
    for observation in result.get("observations",[]):
        code=observation.get("parameter_code")
        value=observation.get("value")
        if code not in display_units:
            display_exclusions.append({"observation_id":observation.get("observation_id"),
                "reason":"parameter_has_no_reviewed_chart_mapping"})
            continue
        if not observation.get("accepted") or not observation.get("event_time") or not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):
            continue
        expected_unit=display_units[code]
        if observation.get("unit") not in unit_aliases.get(expected_unit,{expected_unit}):
            display_exclusions.append({"observation_id":observation.get("observation_id"),
                "reason":"chart_unit_mapping_unqualified"})
            continue
        dt=as_dt(observation["event_time"])
        if dt.utcoffset() is None:
            continue
        t=dt.astimezone(timezone.utc).isoformat()
        sample=observation.get("sample_id")
        segment=observation.get("segment_id")
        matrix=observation.get("matrix")
        equipment=observation.get("equipment_id")
        key=(t,sample,segment,matrix,equipment)
        if sample is not None:
            display_segment="import-sample-"+hashlib.sha256(json.dumps([sample,segment,matrix,equipment]).encode()).hexdigest()[:16]
        elif segment is not None:
            display_segment=segment
        else:
            # No event segmentation was reviewed. Draw isolated points rather
            # than an invented continuous process trace.
            display_segment="import-unsegmented-"+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]
        locator=observation.get("source_locator") or {}
        row=by_identity.setdefault(key,{"timestamp":t,"local_time":observation.get("local_time"),
            "segment_id":display_segment,"evidence_segment_id":segment,"sample_id":sample,
            "matrix":matrix,"equipment_id":equipment,"source_row":locator.get("row"),
            "qc_flags":[],"observation_ids":{},"source_locators":{},
            "availability_by_parameter":{},"display_kind":"point" if sample is not None or segment is None else "segmented_trace"})
        # Even if the importer changes, unresolved replicate values must not
        # silently become a last-row-wins chart value.
        if code in row["observation_ids"]:
            prior=row["observation_ids"].pop(code)
            row.pop(code,None)
            row["source_locators"].pop(code,None)
            row["availability_by_parameter"].pop(code,None)
            row.setdefault("ambiguous_parameters",[]).append(code)
            display_exclusions.append({"observation_ids":[prior,observation["observation_id"]],
                "reason":"nonunique_chart_parameter_at_sample_time"})
        elif code not in row.get("ambiguous_parameters",[]):
            row[code]=value
            row["observation_ids"][code]=observation["observation_id"]
            row["source_locators"][code]=locator
            row["availability_by_parameter"][code]=observation.get("availability_time")
        row["qc_flags"]=sorted(set(row["qc_flags"]+observation.get("qc_flags",[])))
        # A single row label would misattribute simultaneously measured channels
        # that came from different source rows. Tooltips use per-channel locators.
        if row["source_row"]!=locator.get("row"):
            row["source_row"]=None
    result["series"]=sorted(by_identity.values(),key=lambda x:(as_dt(x["timestamp"]),str(x.get("sample_id") or ""),str(x["segment_id"])))
    if result["series"]:
        origin=as_dt(result["series"][0]["timestamp"])
        for row in result["series"]:
            row["elapsed_h"]=(as_dt(row["timestamp"])-origin).total_seconds()/3600
    result["display_exclusions"]=display_exclusions
    from .historical_analysis import analyze_observations,build_hypotheses
    result["historical_analysis"]=analyze_observations(result.get("observations",[]))
    result["hypotheses"]=build_hypotheses(result)
    result["model_results"]={"status":"blocked","reason":"Imported evidence requires reviewed stream, calibration, chemistry, strain and availability mappings before a biological model job"}
    result["evaluation"]={"paired":[],"status":"not_scored","reason":"No qualified prediction/target pairs in this import"}
    result.setdefault("qualification",{})["processing"]="Completed deterministic import QC and chart preparation"
    result["run_hash"]=hashlib.sha256(json.dumps({"run_id":run_id,"evidence_schema":result.get("schema_version"),"sources":result.get("sources"),"mapping":result.get("mapping_preview"),"observations":result.get("observations",[]),"code":[sha(p) for p in sorted((ROOT/"m10/metabocore").glob("*.py"))]},sort_keys=True,allow_nan=False).encode()).hexdigest()
    save_result(result,folder)
    return {"run_id":run_id,"status":"completed","model_status":"blocked","observations":len(result.get("observations",[]))}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--kind",choices=["historical","model_regression","kinetic_scenario"],default="historical");parser.add_argument("--run",default="August");parser.add_argument("--job-id",default="cli")
    args=parser.parse_args();PRIVATE.mkdir(parents=True,exist_ok=True)
    if args.kind=="historical":result=historical(args.run) if args.run in ("August","May") else review_import(args.run)
    elif args.kind=="model_regression":
        from .gem import model_audit_summary
        result=model_audit_summary();write_json(PRIVATE/"model-audit.json",result)
    else:
        from .kinetics import kinetic_reference_case
        result=kinetic_reference_case();write_json(PRIVATE/"kinetic-reference.json",result)
    print(json.dumps(clean(result),ensure_ascii=False))
if __name__=="__main__":main()
