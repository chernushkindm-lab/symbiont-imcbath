import importlib
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("M10_DATA_DIR",str(tmp_path))
    monkeypatch.setenv("M10_ACCESS_TOKEN","test-token-with-more-than-32-characters")
    import metabocore.api
    app=importlib.reload(metabocore.api)
    with TestClient(app.app) as c: yield c,app

def test_all_private_surfaces_deny_anonymous(client):
    c,_=client
    for url in ("/api/v1/runs","/api/v1/kinetics/reference","/api/v1/audit","/api/v1/openapi.json","/api/v1/microscopy","/api/v1/runs/A/exports/result.json","/assets/app.js"):
        assert c.get(url).status_code==401
    assert c.get("/",follow_redirects=False).status_code==303
    assert c.get("/healthz").json()=={"status":"ok"}

def signin(c):
    response=c.post("/login",data={"key":"test-token-with-more-than-32-characters"},follow_redirects=False)
    assert response.status_code==303
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]

def test_session_origin_and_host_boundary(client):
    c,_=client;signin(c)
    assert c.get("/api/v1/runs").status_code==200
    assert c.post("/api/v1/logout",headers={"origin":"https://untrusted.invalid"}).status_code==403
    assert c.post("/api/v1/logout",headers={"origin":"null"}).status_code==403
    assert c.get("/api/v1/runs").headers["referrer-policy"]=="same-origin"
    assert c.get("/api/v1/runs",headers={"host":"evil.example"}).status_code==400
    c.post("/api/v1/logout")
    assert c.get("/api/v1/runs").status_code==401

def test_code_upload_rejected(client):
    c,_=client;signin(c)
    assert c.post("/api/v1/imports/preview",files={"file":("x.ipynb",b"{}")}).status_code==415

def test_normalized_upload_export_and_duplicate_protection(client):
    c,api=client;signin(c)
    raw=b'timestamp,parameter_code,raw_value,raw_unit\n2026-08-30T22:00:00+05:00,pH,"7,1",1\n2026-08-30T23:00:00+05:00,pH,#DIV/0!,1\n'
    preview=c.post("/api/v1/imports/preview",files={"file":("example.csv",raw)})
    assert preview.status_code==200
    ident=preview.json()["import_id"]
    request={"run_id":"upload-regression","mapping":{x:x for x in ("timestamp","parameter_code","raw_value","raw_unit")}}
    result=c.post(f"/api/v1/imports/{ident}/commit",json=request)
    assert result.status_code==200,result.text
    obs=c.get("/api/v1/runs/upload-regression/observations").json()["rows"]
    assert obs[0]["value"]==7.1
    assert obs[1]["value"] is None
    assert all(o["availability_time"] is None for o in obs)
    assert c.get("/api/v1/runs/upload-regression/exports/observations.csv").status_code==200
    assert c.get("/api/v1/runs/upload-regression/exports/observations.parquet").status_code==200
    assert c.post(f"/api/v1/imports/{ident}/commit",json=request).status_code==409
    assert (api.PRIVATE/"imports"/ident/"original.csv").read_bytes()==raw

def test_job_schema_and_path_validation(client):
    c,_=client;signin(c)
    assert c.post("/api/v1/jobs",json={"kind":"shell","command":"anything"}).status_code==422
    assert c.get("/api/v1/runs/bad.id").status_code==400
    assert c.get("/api/v1/runs/X/observations?limit=50000").status_code==400

def test_oversized_upload_rejected(client):
    c,api=client;signin(c)
    response=c.post("/api/v1/imports/preview",files={"file":("large.csv",b"a"*(api.MAX_UPLOAD+1))})
    assert response.status_code==413

# These fixtures contain synthetic software-check evidence only.
def review_run(api):
    import json
    folder=api.PRIVATE/"runs"/"SOFTWARE-CHECK-REVIEWS"
    folder.mkdir(parents=True)
    data={"run_id":"SOFTWARE-CHECK-REVIEWS","run_hash":"a"*64,
          "hypotheses":[{"hypothesis_id":"synthetic:hypothesis:one"},{"hypothesis_id":"synthetic:hypothesis:two"}],
          "observations":[{"observation_id":"synthetic:observation:one"}],
          "sources":[{"source_id":"synthetic:source:one"}],
          "qualification":{"causality":"unestablished; synthetic test fixture"}}
    path=folder/"result.json"
    path.write_text(json.dumps(data),encoding="utf-8")
    return path,data


def review_payload(**changes):
    data={"hypothesis_id":"synthetic:hypothesis:one","status":"deferred",
          "reason":"Synthetic software test only; no research decision.",
          "evidence_ids":["synthetic:observation:one","synthetic:source:one"]}
    data.update(changes)
    return data


REVIEW_URL="/api/v1/runs/SOFTWARE-CHECK-REVIEWS/hypothesis-reviews"


def test_hypothesis_reviews_deny_anonymous_read_and_write(client):
    c,api=client
    review_run(api)
    assert c.get(REVIEW_URL).status_code==401
    assert c.post(REVIEW_URL,json=review_payload()).status_code==401
    assert not (api.PRIVATE/"reviews").exists()


def test_hypothesis_reviews_append_persist_reload_and_preserve_run(client):
    import json
    from datetime import datetime
    c,api=client;signin(c)
    run_path,data=review_run(api)
    original=run_path.read_bytes()
    assert c.get(REVIEW_URL).json()["reviews"]==[]
    first=c.post(REVIEW_URL,json=review_payload(reason="  Synthetic test review.  "))
    assert first.status_code==201,first.text
    record=first.json()
    assert record["revision"]==1 and record["reason"]=="Synthetic test review."
    assert record["run_hash"]==data["run_hash"]
    assert datetime.fromisoformat(record["reviewed_at"]).utcoffset().total_seconds()==0
    log=api.PRIVATE/"reviews"/"SOFTWARE-CHECK-REVIEWS.jsonl"
    prefix=log.read_bytes()
    second=c.post(REVIEW_URL,json=review_payload(status="accepted_as_working",evidence_ids=[]))
    assert second.status_code==201 and second.json()["revision"]==2
    assert log.read_bytes().startswith(prefix)
    api=importlib.reload(api)
    with TestClient(api.app) as restarted:
        signin(restarted)
        history=restarted.get(REVIEW_URL).json()
        assert history["reviews"]==[record,second.json()]
        assert history["latest"][record["hypothesis_id"]]==second.json()
        third=restarted.post(REVIEW_URL,json=review_payload(status="rejected"))
        assert third.status_code==201 and third.json()["revision"]==3
    assert run_path.read_bytes()==original
    assert [json.loads(line)["revision"] for line in log.read_text(encoding="utf-8").splitlines()]==[1,2,3]


def test_hypothesis_reviews_reject_missing_hypothesis_and_evidence(client):
    c,api=client;signin(c);review_run(api)
    response=c.post(REVIEW_URL,json=review_payload(hypothesis_id="other-run:hypothesis"))
    assert response.status_code==404
    response=c.post(REVIEW_URL,json=review_payload(evidence_ids=["unknown-observation"]))
    assert response.status_code==422
    assert response.json()["detail"]["unknown_ids"]==["unknown-observation"]
    assert not (api.PRIVATE/"reviews").exists()


@pytest.mark.parametrize("changes",[
    {"reason":""},{"reason":" \n\t "},{"reason":"x"*2001},
    {"status":"proven_causal"},{"evidence_ids":["synthetic:source:one"]*101},
    {"evidence_ids":[""]},{"evidence_ids":["x"*201]},
    {"revision":900},{"reviewed_at":"1900-01-01T00:00:00Z"},
])
def test_hypothesis_review_schema_bounds_and_server_fields(client,changes):
    c,api=client;signin(c);review_run(api)
    assert c.post(REVIEW_URL,json=review_payload(**changes)).status_code==422
    assert not (api.PRIVATE/"reviews").exists()


def test_hypothesis_reviews_old_run_hash_remains_history_not_current(client):
    import json
    c,api=client;signin(c)
    path,data=review_run(api)
    record=c.post(REVIEW_URL,json=review_payload()).json()
    data["run_hash"]="b"*64
    path.write_text(json.dumps(data),encoding="utf-8")
    response=c.get(REVIEW_URL)
    assert response.status_code==200
    assert response.json()["reviews"]==[record]
    assert response.json()["latest"]=={}
    newer=c.post(REVIEW_URL,json=review_payload()).json()
    assert newer["revision"]==2 and newer["run_hash"]=="b"*64
    assert c.get(REVIEW_URL).json()["latest"][newer["hypothesis_id"]]==newer


def test_hypothesis_review_partial_log_is_not_truncated_or_appended(client):
    c,api=client;signin(c);review_run(api)
    assert c.post(REVIEW_URL,json=review_payload()).status_code==201
    log=api.PRIVATE/"reviews"/"SOFTWARE-CHECK-REVIEWS.jsonl"
    with log.open("ab") as stream: stream.write(b'{"incomplete":')
    before=log.read_bytes()
    assert c.get(REVIEW_URL).status_code==500
    assert c.post(REVIEW_URL,json=review_payload()).status_code==500
    assert log.read_bytes()==before