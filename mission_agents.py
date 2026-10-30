"""Post-Vault deterministic evidence agents. No model, broker, network, or MQL execution.

Static engineering readiness is not safety, native compilation, or profitability.
The four processes read a bounded inert snapshot and produce an evidence plan.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
import fcntl
from worker_fleet import atomic_json

ROLES = ('EVIDENCE_TRIAGE', 'EA_ENGINEERING', 'VALIDATION_REVIEW', 'MISSION_PLANNER')
UI_ROLES = dict(zip(ROLES, ('TRIAGE','ENGINEER','VALIDATOR','DIRECTOR')))
TIMEOUT = 15
SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
KNOWN_LICENSES = {'MIT','Apache-2.0','BSD-2-Clause','BSD-3-Clause','ISC','GPL-3.0','GPL-3.0-only','GPL-3.0-or-later','GPL-2.0','GPL-2.0-only','GPL-2.0-or-later','LGPL-3.0','MPL-2.0'}


def _read_source(root, item):
    ident = item.get('id')
    if not isinstance(ident, str) or not SAFE_ID.fullmatch(ident):
        return {'id': str(ident)[:100], 'source_error': 'INVALID_CANDIDATE_ID'}
    path = Path(root)/'generated'/(ident+'.mq5')
    if path.is_symlink():
        return {**item, 'source_error':'SYMLINK_REJECTED'}
    try:
        if path.stat().st_size > 250_000: raise ValueError('SOURCE_TOO_LARGE')
        raw=path.read_bytes()
        return {**item, 'text':raw.decode('utf-8'), 'actual_sha256':hashlib.sha256(raw).hexdigest()}
    except (OSError, ValueError, UnicodeError) as error:
        return {**item, 'source_error':type(error).__name__}


def _request(root, status, fleet):
    if not isinstance(status,dict) or not isinstance(fleet,dict):raise ValueError('Evidence must be objects')
    candidates=status.get('generated_candidates',[])
    if not isinstance(candidates,list) or len(candidates)>30:raise ValueError('Candidate bound exceeded')
    allowed=('id','kind','upstream','commit','license','sha256','execution','compile_status','performance')
    # Deliberately exclude timestamps, worker PIDs, and provider claims from identity.
    source=[_read_source(root,{k:item.get(k) for k in allowed}) for item in candidates if isinstance(item,dict)]
    repos=[{k:r.get(k) for k in ('repository','commit','license')} for r in status.get('repositories',[])[:30] if isinstance(r,dict)]
    counts=fleet.get('counts',{})
    request={'candidates':source,'repositories':repos,'fleet_status':fleet.get('status'),
             'fleet_counts':{k:counts.get(k,0) for k in ('workers','completed','failed','timed_out')}}
    fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True,allow_nan=False).encode()).hexdigest()
    request['input_fingerprint']=fingerprint
    return request


def evaluate(role, request):
    if role not in ROLES:raise ValueError('Unknown mission role')
    candidates=request.get('candidates',[])
    if not isinstance(candidates,list) or len(candidates)>30:raise ValueError('Invalid candidate scope')
    common={'agent':role,'model_provider':None,'broker_commands':0,'external_code_executed':False,
            'profitability':'UNPROVEN','automatic_promotion':False}
    if role=='EVIDENCE_TRIAGE':
        rows=[]
        for c in candidates:
            expected=c.get('sha256');actual=c.get('actual_sha256')
            valid=bool(isinstance(expected,str) and SHA.fullmatch(expected) and expected==actual and not c.get('source_error'))
            reused=c.get('kind')=='REUSED_UPSTREAM_SIGNAL_LOGIC'
            license_id=c.get('license')
            # A fresh missing license cannot inherit an old repository license silently.
            recognized=license_id in KNOWN_LICENSES if reused else c.get('kind')=='GENERATED_FROM_EXISTING_TESTER_BASELINE'
            blockers=[]
            if not valid:blockers.append('SOURCE_HASH_OR_FILE_INVALID')
            if not recognized:blockers.append('LICENSE_PROVENANCE_UNCONFIRMED')
            if reused and not re.fullmatch(r'[a-f0-9]{40}',str(c.get('commit') or '')):blockers.append('UPSTREAM_COMMIT_NOT_PINNED')
            rows.append({'id':c.get('id'),'hash_verified':valid,'license':license_id,
                         'license_metadata_recognized':recognized,'source_origin':'UPSTREAM' if reused else 'LOCAL_BASELINE',
                         'blockers':blockers,'next_action':'REPAIR_PROVENANCE' if blockers else 'STATIC_ENGINEERING_AUDIT'})
        return {**common,'candidates':rows,'files_verified':sum(r['hash_verified'] for r in rows),
                'repository_count':len(request.get('repositories',[])),
                'notice':'License metadata recognition is not a distribution-obligation review.'}
    previous=request.get('stage_results',{})
    triage={r['id']:r for r in previous.get('EVIDENCE_TRIAGE',{}).get('candidates',[])}
    if role=='EA_ENGINEERING':
        rows=[]
        patterns={'tester_guard':r'if\s*\([^;]*!\s*MQLInfoInteger\s*\(\s*MQL_TESTER\s*\)[^;]*\)\s*(?:\{\s*)?return\s+INIT_FAILED',
                  'stop_loss':r'request\.sl\s*=|\bStopLoss\b',
                  'take_profit':r'request\.tp\s*=|\bTakeProfit\b',
                  'risk_sizing':r'\bRiskLots\s*\(|\briskBudget\b',
                  'order_check':r'\bOrderCheck\s*\(',
                  'magic_scope':r'POSITION_MAGIC|JarvisMagic',
                  'signal_only':r'STRATEGY_TESTER_SIGNAL_LOG_ONLY|SIGNAL.?ONLY|signal.only'}
        for c in candidates:
            # Remove comments before hints, so labels alone cannot satisfy guards.
            text=c.get('text') or ''
            code=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
            hints={name:bool(re.search(pattern,code,re.I)) for name,pattern in patterns.items()}
            signal_only=c.get('execution')=='STRATEGY_TESTER_SIGNAL_LOG_ONLY'
            checks=['tester_guard'] if signal_only else ['tester_guard','stop_loss','take_profit','risk_sizing','order_check','magic_scope']
            missing=[key for key in checks if not hints[key]]
            blockers=list(triage.get(c.get('id'),{}).get('blockers',['TRIAGE_MISSING']))
            blockers.extend('STATIC_HINT_MISSING_'+key.upper() for key in missing)
            rows.append({'id':c.get('id'),'source_sha256':c.get('actual_sha256'),'static_hints':hints,
                         'engineering_score':sum(hints[k] for k in checks)/len(checks),
                         'score_basis':'Fraction of expected static engineering hints; not a profit ranking',
                         'signal_only':signal_only,'blockers':blockers,
                         'patch_requirements':missing,'source_modified':False})
        return {**common,'candidates':rows,'notice':'Static text hints can be misleading; native control-flow and runtime validation remain required.'}
    engineering=previous.get('EA_ENGINEERING',{}).get('candidates',[])
    if role=='VALIDATION_REVIEW':
        rows=[]
        for row in engineering:
            blockers=list(row['blockers'])
            blockers+=['NATIVE_MT5_COMPILE_NOT_VERIFIED','SIGNAL_PARITY_NOT_VERIFIED','BROKER_COST_FORWARD_DEMO_NOT_VERIFIED']
            rows.append({'id':row['id'],'status':'HOLD_FOR_EVIDENCE','blockers':blockers,
                         'required_evidence':[
                             {'type':'NATIVE_MT5_COMPILER_REPORT','candidate_sha256':row.get('source_sha256'),'status':'MISSING'},
                             {'type':'SIGNAL_PARITY_REPORT','candidate_sha256':row.get('source_sha256'),'status':'MISSING'},
                             {'type':'ISOLATED_DEMO_FORWARD_REPORT','include':['spread','commission','slippage','drawdown','sample_size'],'status':'MISSING'}],
                         'compile_launched':False,'backtest_launched':False,'trading_enabled':False})
        return {**common,'candidates':rows,'verified_winner':None}
    validation=previous.get('VALIDATION_REVIEW',{}).get('candidates',[])
    ranking=sorted(engineering,key=lambda r:(bool(r['blockers']),-r['engineering_score'],r['id']))
    tasks=[]
    for row in validation:
        cid=row['id'];eng=next((r for r in engineering if r['id']==cid),{})
        if eng.get('blockers'):
            tasks.append({'candidate':cid,'task':'REPAIR_SOURCE_OR_PROVENANCE','owner':'EA_ENGINEERING',
                          'status':'NEEDS_IMPLEMENTATION_REVIEW','requirements':eng['blockers']})
        tasks.append({'candidate':cid,'task':'NATIVE_MT5_COMPILE_AND_SIGNAL_PARITY','owner':'VALIDATION_REVIEW',
                      'status':'WAITING_FOR_ISOLATED_MT5_VALIDATION','requirements':row['required_evidence'][:2]})
        tasks.append({'candidate':cid,'task':'COST_AWARE_FORWARD_DEMO','owner':'VALIDATION_REVIEW',
                      'status':'BLOCKED_BY_NATIVE_VALIDATION','requirements':row['required_evidence'][2:]})
    return {**common,'objective':'Find or build an EA with verified engineering and demo-performance evidence',
            'objective_status':'NOT_ACHIEVED','verified_winner':None,
            'engineering_priority':[{'id':r['id'],'score':r['engineering_score'],'basis':r['score_basis']} for r in ranking],
            'tasks':tasks,'next_move':tasks[0] if tasks else {'task':'DISCOVER_OR_BUILD_CANDIDATES','status':'NEEDS_SOURCE_EVIDENCE'},
            'notice':'No native or performance evidence is supplied by this deterministic pipeline. It cannot declare an EA profitable.'}


def _alive(pid):
    try:os.kill(int(pid),0);return True
    except (OSError,TypeError,ValueError):return False


def read_status(root):
    try:
        state=json.loads((Path(root)/'data/mission-progress.json').read_text())
        if state.get('status')=='RUNNING' and not _alive(state.get('supervisor_pid')):
            state['status']='INTERRUPTED'
            for node in state.get('nodes',[]):
                if node['status'] in ('QUEUED','RUNNING'):node['status']='INTERRUPTED'
        return state
    except (OSError,ValueError):return {'status':'NOT_STARTED','nodes':[],'objective_status':'NOT_ACHIEVED'}


def _persist(root,state):
    atomic_json(root/'data/mission-progress.json',state)
    atomic_json(root/'generated/mission-progress.json',state)


def _report(root,state):
    planner=state.get('results',{}).get('MISSION_PLANNER',{})
    lines=['# Mark 2 post-Vault mission review','',f"Pipeline: {state['status']}",
           'Objective: NOT ACHIEVED. No verified winning EA.','',
           'Four real deterministic tool processes reviewed saved evidence. No model call, broker command, MQL execution, or new backtest.',
           '','## Engineering priority (not profitability)','']
    for row in planner.get('engineering_priority',[]):lines.append(f"- {row['id']}: {row['score']:.2f} static-hint coverage; native validation still missing.")
    lines+=['','## Next tasks','']
    for task in planner.get('tasks',[]):lines.append(f"- {task['candidate']} / {task['task']}: {task['status']}")
    lines+=['','Native compiler, signal-parity and isolated cost-aware forward-demo reports must match the candidate source hash before any promotion can be considered.','']
    path=root/'generated/mission-review.md';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(lines))
    for candidate in state.get('results',{}).get('EVIDENCE_TRIAGE',{}).get('candidates',[]):
        ident=candidate.get('id')
        if not isinstance(ident,str) or not SAFE_ID.fullmatch(ident):continue
        detail={'candidate':ident,'mission_run_id':state['run_id'],'profitability':'UNPROVEN','trading_enabled':False}
        for role in ROLES:
            matches=[row for row in state.get('results',{}).get(role,{}).get('candidates',[]) if row.get('id')==ident]
            if matches:detail[role]=matches[0]
        detail['next_tasks']=[task for task in planner.get('tasks',[]) if task['candidate']==ident]
        atomic_json(root/'generated/mission-reviews'/(ident+'.json'),detail)


def run_once(root,status,fleet):
    root=Path(root).resolve();(root/'data').mkdir(parents=True,exist_ok=True)
    request=_request(root,status,fleet)
    with (root/'data/mission.run.lock').open('a+') as lease:
        try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return read_status(root)
        old=read_status(root)
        if old.get('input_fingerprint')==request['input_fingerprint'] and old.get('status')=='COMPLETED':return old
        run_id='mission-'+uuid.uuid4().hex[:12];now=time.time()
        state={'schema_version':1,'run_id':run_id,'input_fingerprint':request['input_fingerprint'],
               'status':'RUNNING','started_unix':now,'completed_unix':None,'supervisor_pid':os.getpid(),
               'objective_status':'NOT_ACHIEVED','verdict':'WAITING_FOR_NATIVE_VALIDATION_AND_DEMO_EVIDENCE','verified_winner':None,'model_provider':None,
               'broker_commands':0,'external_code_executed':False,'results':{},'nodes':[]}
        for role in ROLES:state['nodes'].append({'id':run_id+'/'+role.lower(),'name':role.replace('_',' ').title(),
             'task':role,'role':UI_ROLES[role],'ui_node':UI_ROLES[role],'kind':'DETERMINISTIC_MISSION_WORKER','status':'QUEUED','pid':None,'started_unix':None,'completed_unix':None,'result':None})
        _persist(root,state)
        for node in state['nodes']:
            process=None
            try:
                process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child',node['task']],
                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                     env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','WINDIR')})
                node.update(status='RUNNING',pid=process.pid,started_unix=time.time());_persist(root,state)
                payload={**request,'stage_results':state['results']}
                output,error=process.communicate(json.dumps(payload,allow_nan=False),timeout=TIMEOUT)
                if process.returncode:raise ValueError('Child process failed: '+error[:200])
                result=json.loads(output);node.update(status='COMPLETED',completed_unix=time.time(),result=result)
                state['results'][node['task']]=result;_persist(root,state)
            except Exception as error:
                if process and process.poll() is None:process.kill();process.communicate()
                node.update(status='FAILED',completed_unix=time.time(),error=str(error)[:250]);state['status']='FAILED';break
        if state['status']=='RUNNING':state['status']='COMPLETED'
        state['completed_unix']=time.time();state['next_tasks']=state['results'].get('MISSION_PLANNER',{}).get('tasks',[])
        _persist(root,state);_report(root,state);return state


def kickoff(root,status,fleet):
    root=Path(root).resolve();(root/'data').mkdir(parents=True,exist_ok=True)
    try:request=_request(root,status,fleet)
    except (ValueError,TypeError) as error:return {'status':'INVALID_INPUT','pid':None,'error':str(error)}
    with (root/'data/mission.launch.lock').open('a+') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        old=read_status(root)
        if old.get('status')=='RUNNING':return {'status':'ALREADY_RUNNING','pid':old.get('supervisor_pid')}
        if old.get('status')=='COMPLETED' and old.get('input_fingerprint')==request['input_fingerprint']:
            return {'status':'UP_TO_DATE','pid':None,'run_id':old.get('run_id')}
        pid_path=root/'data/mission-supervisor.pid'
        try:pid=int(pid_path.read_text())
        except (OSError,ValueError):pid=None
        if pid and _alive(pid):return {'status':'ALREADY_RUNNING','pid':pid}
        # Only sanitized metadata and candidate source data were fingerprinted. The
        # launch file is local evidence, not credentials or an external upload.
        input_path=root/'data/mission-input.json'
        metadata_keys=('id','kind','upstream','commit','license','sha256','execution','compile_status','performance')
        launch_status={'generated_candidates':[{k:c.get(k) for k in metadata_keys} for c in request['candidates']], 'repositories':request['repositories']}
        atomic_json(input_path,{'status':launch_status,'fleet':{'status':request['fleet_status'],'counts':request['fleet_counts']}})
        with (root/'data/mission-supervisor.log').open('a') as log:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--once','--root',str(root),'--input',str(input_path)],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,cwd=str(root),
                env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','WINDIR')})
        pid_path.write_text(str(process.pid));return {'status':'STARTED','pid':process.pid}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default=str(Path(__file__).resolve().parent))
    parser.add_argument('--once',action='store_true');parser.add_argument('--input');parser.add_argument('--child',choices=ROLES);args=parser.parse_args()
    if args.child:
        request=json.loads(sys.stdin.read(8_000_001));print(json.dumps(evaluate(args.child,request),allow_nan=False));return 0
    root=Path(args.root)
    source=json.loads(Path(args.input).read_text()) if args.input else {'status':json.loads((root/'data/status.json').read_text()),'fleet':json.loads((root/'data/worker-fleet.json').read_text())}
    state=run_once(root,source['status'],source['fleet']);return 0 if state['status']=='COMPLETED' else 1

if __name__=='__main__':raise SystemExit(main())
