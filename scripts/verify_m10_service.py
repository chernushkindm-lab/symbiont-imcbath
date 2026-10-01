"""Exercise real loopback workers without exporting private credentials or raw data."""
import argparse, json, os, time, subprocess
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path(os.environ.get('M10_DATA_DIR',str(ROOT/'m10/private')))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--historical',action='store_true');args=parser.parse_args()
    token=os.environ.get('M10_ACCESS_TOKEN') or (PRIVATE/'access-token.txt').read_text(encoding='utf-8').strip()
    checks=[];replays=[]
    with httpx.Client(base_url='http://127.0.0.1:8050',headers={'Authorization':'Bearer '+token},timeout=120) as c:
        def job(kind,run='August'):
            response=c.post('/api/v1/jobs',json={'kind':kind,'run':run});response.raise_for_status();identifier=response.json()['id']
            end=time.monotonic()+200
            while time.monotonic()<end:
                time.sleep(1)
                r=c.get('/api/v1/jobs/'+identifier);r.raise_for_status();state=r.json()
                if state['status'] not in ('queued','running'):
                    assert state['status']=='completed',state
                    checks.append({'kind':kind,'run':run,'job_id':identifier,'status':state['status']})
                    print(json.dumps(checks[-1]),flush=True);return state
            raise RuntimeError('Job did not finish within service deadline')
        job('model_regression')
        audit=c.get('/api/v1/audit').json()
        assert audit['model_integrity']=='verified'
        assert audit['structural_audit_status']=='completed_with_findings'
        job('kinetic_scenario')
        kinetic=c.get('/api/v1/kinetics/reference').json()
        assert kinetic['classification']=='assumed/synthetic'
        assert kinetic['conservation']['maximum_carbon_residual_g']<=kinetic['conservation']['tolerance_g']
        if args.historical:
            for run in ('August','May'):
                job('historical',run)
                rid='LAB005-2026-08' if run=='August' else 'LAB005-2026-05'
                result=c.get('/api/v1/runs/'+rid).json()
                replays.append({'run_id':rid,'run_hash':result['run_hash'],'observation_count':result['observation_count'],'created_at':result['created_at']})
                assert result['observation_count']>10000
                assert result.get('input_set')
                assert len(result['hypotheses'])==8
                assert result['evaluation']['status']=='not_scored'
                if run=='August':
                    model=result['model_results']['conditional_window']['result']
                    assert model['solver_status']=='optimal'
                    assert model['model_audit']['structural_audit_status']=='completed_with_findings'
                else:assert result['model_results']['conditional_window']['status']=='blocked'
                for name in ('observations.csv','observations.parquet','result.json','manifest.json','chart.svg','chart.png','report.html','evaluation.csv'):
                    export=c.get(f'/api/v1/runs/{rid}/exports/{name}');export.raise_for_status();assert export.content
                job('historical',run)
                log=(PRIVATE/'jobs'/f"{checks[-1]['job_id']}.log").read_text(encoding='utf-8')
                assert 'verified_hit' in log,'Deterministic cache was not reused'
    report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'replays':replays,'model_hashes':audit['artifact_hashes'],'status':'passed','checked_at_epoch':time.time(),'historical':args.historical,'checks':checks,'audit_counts':audit['audit_counts'],'kinetic_carbon_residual_g':kinetic['conservation']['maximum_carbon_residual_g']}
    target=PRIVATE/'verification';target.mkdir(parents=True,exist_ok=True)
    (target/'service-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','worker_jobs':len(checks),'historical':args.historical}))
if __name__=='__main__':main()