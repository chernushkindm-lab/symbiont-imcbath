"""Authenticated, loopback-only local M10 API. Never executes uploaded code."""
from __future__ import annotations
import asyncio, csv, hashlib, hmac, io, json, os, secrets, sys, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(os.getenv("M10_DATA_DIR", str(ROOT / "m10/private"))).resolve()
PRIVATE.mkdir(parents=True, exist_ok=True)
SECRET_FILE = PRIVATE / "access-token.txt"
if os.getenv("M10_ACCESS_TOKEN"):
    TOKEN = os.environ["M10_ACCESS_TOKEN"]
else:
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try: SECRET_FILE.chmod(0o600)
        except OSError: pass
    TOKEN = SECRET_FILE.read_text(encoding="utf-8").strip()
if len(TOKEN) < 24: raise RuntimeError("M10_ACCESS_TOKEN must contain at least 24 characters")
app = FastAPI(title="SYMBIONT M10", version="0.2.0", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1","localhost","testserver"])
sessions: dict[str,float] = {}
attempts: dict[str,list[float]] = {}
jobs: dict[str,dict] = {}
processes: dict[str,asyncio.subprocess.Process] = {}
MAX_UPLOAD = 8 * 1024 * 1024
review_lock = Lock()

def authorised(request: Request) -> bool:
    bearer = request.headers.get("authorization","")
    if bearer.startswith("Bearer ") and hmac.compare_digest(bearer[7:], TOKEN): return True
    sid = request.cookies.get("m10_session","")
    return bool(sid and sessions.get(sid,0) > time.time())

@app.middleware("http")
async def protect(request, call_next):
    origin=request.headers.get("origin")
    expected=str(request.base_url).rstrip("/")
    if request.method not in ("GET","HEAD","OPTIONS") and origin and origin != expected:
        return JSONResponse({"detail":"Cross-origin mutation denied"},status_code=403)
    if request.url.path not in ("/login","/healthz") and not authorised(request):
        if request.url.path == "/": return RedirectResponse("/login",status_code=303)
        return JSONResponse({"detail":"Authentication required"},status_code=401)
    response=await call_next(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="same-origin"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'"
    return response

@app.get("/healthz")
def health(): return {"status":"ok"}

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return '<!doctype html><html><meta charset="utf-8"><title>SYMBIONT · Local access</title><body style="font:18px system-ui;background:#f4f8f9;color:#2b3d45;padding:12vh 12vw"><h1>SYMBIONT / LAB 005</h1><p>Private local scientific workspace</p><form method="post"><label>Local access key<br><input type="password" name="key" required autocomplete="current-password" style="padding:14px;width:360px;max-width:85%"></label><p><button style="padding:12px 24px">Open workspace</button></p></form><p style="font-size:14px">The key is stored in the private access-token.txt file beside this service’s run storage.</p></body></html>'

@app.post("/login")
async def login(request:Request,key:str=Form(...)):
    ip=request.client.host if request.client else "unknown"
    recent=[t for t in attempts.get(ip,[]) if time.time()-t < 300]
    if len(recent)>=10: raise HTTPException(429,"Try again in five minutes")
    if not hmac.compare_digest(key,TOKEN):
        attempts[ip]=recent+[time.time()]
        raise HTTPException(401,"Invalid key")
    attempts.pop(ip,None)
    sid=secrets.token_urlsafe(32); sessions[sid]=time.time()+8*3600
    response=RedirectResponse("/",status_code=303)
    response.set_cookie("m10_session",sid,httponly=True,samesite="strict",max_age=8*3600,secure=request.url.scheme=="https")
    return response

@app.post("/api/v1/logout")
def logout(request:Request):
    sessions.pop(request.cookies.get("m10_session",""),None)
    response=JSONResponse({"status":"signed_out"}); response.delete_cookie("m10_session")
    return response

@app.get("/")
def index(): return FileResponse(ROOT/"m10/web/index.html")

@app.get("/assets/{name}")
def asset(name:str):
    if name not in ("app.js","style.css"): raise HTTPException(404)
    return FileResponse(ROOT/"m10/web"/name)

def run_path(run_id):
    if not run_id.replace("-","").replace("_","").isalnum(): raise HTTPException(400,"Invalid run ID")
    p=PRIVATE/"runs"/run_id/"result.json"
    if not p.exists(): raise HTTPException(404,"Run not found")
    return p

def load_run(run_id): return json.loads(run_path(run_id).read_text(encoding="utf-8"))

@app.get("/api/v1/runs")
def runs():
    result=[]
    for p in sorted((PRIVATE/"runs").glob("*/result.json")):
        try:
            r=json.loads(p.read_text(encoding="utf-8"))
            result.append({k:r.get(k) for k in ("run_id","coverage","qualification","created_at","run_hash")})
        except (ValueError,OSError): continue
    return result

@app.get("/api/v1/runs/{run_id}")
def run(run_id:str):
    r=load_run(run_id)
    r.pop("observations",None)
    return r

@app.get("/api/v1/runs/{run_id}/observations")
def observations(run_id:str,offset:int=0,limit:int=200,parameter:str|None=None):
    if offset<0 or not 1<=limit<=1000: raise HTTPException(400,"Invalid page")
    rows=load_run(run_id).get("observations",[])
    if parameter: rows=[r for r in rows if r.get("parameter_code")==parameter]
    return {"total":len(rows),"offset":offset,"rows":rows[offset:offset+limit]}

@app.get("/api/v1/runs/{run_id}/exports/{name}")
def export(run_id:str,name:str):
    allowed={"observations.csv","observations.parquet","result.json","manifest.json","chart.svg","chart.png","report.html","evaluation.csv"}
    if name not in allowed: raise HTTPException(404)
    p=run_path(run_id).parent/name
    if not p.exists(): raise HTTPException(404,"Export unavailable")
    return FileResponse(p,filename=name)

class HypothesisReviewRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    hypothesis_id:str=Field(min_length=1,max_length=200)
    status:Literal["accepted_as_working","rejected","deferred"]
    reason:str=Field(min_length=1,max_length=2000)
    evidence_ids:list[str]=Field(default_factory=list,max_length=100)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls,value):
        value=value.strip()
        if not value: raise ValueError("A nonblank review reason is required")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def bounded_evidence_ids(cls,values):
        if any(not value.strip() or len(value)>200 for value in values):
            raise ValueError("Evidence IDs must contain 1 to 200 nonblank characters")
        return list(dict.fromkeys(values))


def read_hypothesis_reviews(run_id):
    """Read committed entries; corruption must never be silently truncated."""
    path=PRIVATE/"reviews"/f"{run_id}.jsonl"
    if not path.exists(): return []
    try:
        text=path.read_text(encoding="utf-8")
        if text and not text.endswith("\n"): raise ValueError("Incomplete review entry")
        records=[json.loads(line) for line in text.splitlines()]
        for revision,record in enumerate(records,1):
            if not isinstance(record,dict) or record.get("run_id")!=run_id or record.get("revision")!=revision:
                raise ValueError("Invalid review log sequence")
        return records
    except (OSError,ValueError) as exc:
        raise HTTPException(500,"Review history cannot be verified; no append performed") from exc


@app.get("/api/v1/runs/{run_id}/hypothesis-reviews")
def hypothesis_reviews(run_id:str):
    current=load_run(run_id)
    hypothesis_ids={item.get("hypothesis_id") for item in current.get("hypotheses",[])}
    with review_lock:
        records=read_hypothesis_reviews(run_id)
    latest={item["hypothesis_id"]:item for item in records
            if item.get("run_hash")==current.get("run_hash") and item.get("hypothesis_id") in hypothesis_ids}
    return {"run_id":run_id,"run_hash":current.get("run_hash"),"reviews":records,"latest":latest}


@app.post("/api/v1/runs/{run_id}/hypothesis-reviews",status_code=201)
def add_hypothesis_review(run_id:str,request:HypothesisReviewRequest):
    # Serialize revision assignment and append in the supported single-process service.
    with review_lock:
        current=load_run(run_id)
        if request.hypothesis_id not in {item.get("hypothesis_id") for item in current.get("hypotheses",[])}:
            raise HTTPException(404,"Hypothesis does not exist in the current run")
        evidence_ids={item.get("observation_id") for item in current.get("observations",[])}
        evidence_ids.update(item.get("source_id") for item in current.get("sources",[]))
        unknown=[item for item in request.evidence_ids if item not in evidence_ids]
        if unknown: raise HTTPException(422,{"message":"Evidence IDs do not exist in the current run","unknown_ids":unknown})
        records=read_hypothesis_reviews(run_id)
        record={"review_id":uuid.uuid4().hex,"run_id":run_id,"revision":len(records)+1,
                "reviewed_at":datetime.now(timezone.utc).isoformat(),"run_hash":current.get("run_hash"),
                **request.model_dump()}
        path=PRIVATE/"reviews"/f"{run_id}.jsonl"
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("a",encoding="utf-8",newline="\n") as stream:
            stream.write(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n")
            stream.flush()
            os.fsync(stream.fileno())
    return record


@app.get("/api/v1/config")
def config(): return json.loads((ROOT/"m10/config/decisions.json").read_text(encoding="utf-8"))

class JobRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    kind: Literal["historical","model_regression","kinetic_scenario"] = "historical"
    run: str = Field(default="August", pattern=r"^[A-Za-z0-9_-]{1,80}$")

async def execute_job(job_id,request):
    if jobs[job_id]["status"]=="cancelled": return
    jobs[job_id]["status"]="running"
    log=PRIVATE/"jobs"/f"{job_id}.log"; log.parent.mkdir(exist_ok=True)
    command=[sys.executable,"-m","metabocore.worker","--kind",request.kind,"--run",request.run,"--job-id",job_id]
    env=os.environ.copy();env["PYTHONPATH"]=str(ROOT/"m10")+os.pathsep+str(ROOT/"src")
    env["OMP_NUM_THREADS"]="1";env["OPENBLAS_NUM_THREADS"]="1"
    env["M10_DATA_DIR"]=str(PRIVATE)
    with log.open("wb") as stream:
        proc=await asyncio.create_subprocess_exec(*command,cwd=str(ROOT),env=env,stdout=stream,stderr=stream)
        processes[job_id]=proc
        try:
            await asyncio.wait_for(proc.wait(),timeout=180)
            if jobs[job_id]["status"]=="cancelled": return
            jobs[job_id]["status"]="completed" if proc.returncode==0 else "failed"
            jobs[job_id]["exit_code"]=proc.returncode
            if proc.returncode: jobs[job_id]["error"]="Worker failed. Inspect private job log; no result was qualified."
        except asyncio.TimeoutError:
            proc.kill();await proc.wait()
            jobs[job_id].update(status="timed_out",error="Job exceeded 180 seconds")
        finally: processes.pop(job_id,None)
    jobs[job_id]["finished_at"]=time.time()
    (PRIVATE/"jobs"/f"{job_id}.json").write_text(json.dumps(jobs[job_id],indent=2),encoding="utf-8")

@app.post("/api/v1/jobs",status_code=202)
async def submit(request:JobRequest):
    if any(j["status"] in ("queued","running") for j in jobs.values()): raise HTTPException(429,"One scientific job may run at a time")
    job_id=uuid.uuid4().hex
    jobs[job_id]={"id":job_id,"status":"queued","request":request.model_dump(),"created_at":time.time()}
    asyncio.create_task(execute_job(job_id,request))
    return jobs[job_id]

@app.get("/api/v1/jobs/{job_id}")
def job(job_id:str):
    if job_id not in jobs: raise HTTPException(404)
    return jobs[job_id]

@app.delete("/api/v1/jobs/{job_id}")
async def cancel(job_id:str):
    if job_id not in jobs: raise HTTPException(404)
    if jobs[job_id]["status"] not in ("queued","running"): raise HTTPException(409,"Job already finished")
    jobs[job_id]["status"]="cancelled"
    proc=processes.get(job_id)
    if proc and proc.returncode is None: proc.kill();await proc.wait()
    return jobs[job_id]

@app.post("/api/v1/imports/preview")
async def preview(file:UploadFile=File(...)):
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(415,"Only CSV accepted; notebooks, macros and executable files are rejected")
    data=await file.read(MAX_UPLOAD+1)
    if len(data)>MAX_UPLOAD: raise HTTPException(413,"CSV exceeds 8 MiB")
    try: text=data.decode("utf-8-sig")
    except UnicodeDecodeError: raise HTTPException(422,"UTF-8 CSV required")
    try:
        dialect=csv.Sniffer().sniff(text[:8192],delimiters=",;\t")
        rows=list(csv.reader(io.StringIO(text),dialect))
    except csv.Error: raise HTTPException(422,"Could not parse CSV")
    if not rows or len(rows[0])>250 or len(rows)>20001: raise HTTPException(422,"CSV limit: 250 columns / 20000 records")
    import_id=hashlib.sha256(data).hexdigest()
    folder=PRIVATE/"imports"/import_id;folder.mkdir(parents=True,exist_ok=True)
    (folder/"original.csv").write_bytes(data)
    (folder/"preview.json").write_text(json.dumps({"filename":Path(file.filename).name,"sha256":import_id,"delimiter":dialect.delimiter,"rows":len(rows),"headers":rows[0]},ensure_ascii=False),encoding="utf-8")
    return {"import_id":import_id,"rows":len(rows),"headers":rows[0],"preview":rows[1:6],"required_mapping":["timestamp","parameter_code","raw_value","raw_unit"],"qc":"Preview only. Original bytes retained. Missing availability blocks forecast use."}

class MappingRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    mapping:dict[str,str]
    run_id:str=Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    classification:Literal["measured","source-derived"]="measured"

@app.post("/api/v1/imports/{import_id}/commit")
def commit_import(import_id:str,request:MappingRequest):
    if len(import_id)!=64 or any(c not in "0123456789abcdef" for c in import_id): raise HTTPException(400)
    folder=PRIVATE/"imports"/import_id
    if not (folder/"original.csv").exists(): raise HTTPException(404)
    from metabocore.imports import normalise_upload
    from metabocore.worker import save_result
    try: result=normalise_upload(folder,request.model_dump())
    except (ValueError,KeyError) as e: raise HTTPException(422,str(e))
    target=PRIVATE/"runs"/request.run_id
    if target.exists(): raise HTTPException(409,"Run ID already exists; choose a new ID")
    save_result(result,target)
    (folder/"mapping.json").write_text(request.model_dump_json(indent=2),encoding="utf-8")
    return {"run_id":request.run_id,"observations":len(result["observations"]),"qualification":result["qualification"]}

@app.get("/api/v1/audit")
def audit():
    p=PRIVATE/"model-audit.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"status":"not_run"}

@app.get("/api/v1/kinetics/reference")
def kinetic_reference():
    p=PRIVATE/"kinetic-reference.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"status":"not_run","classification":"synthetic implementation reference; not LAB005 calibration"}

@app.get("/api/v1/microscopy")
def microscopy():
    p=PRIVATE/"microscopy.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"images":[],"status":"No images linked to historical samples"}

@app.get("/api/v1/microscopy/{image_id}")
def microscopy_image(image_id:str):
    if not image_id.replace("-","").isalnum(): raise HTTPException(400)
    p=PRIVATE/"microscopy"/f"{image_id}.png"
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

@app.get("/api/v1/openapi.json")
def schema(): return app.openapi()
