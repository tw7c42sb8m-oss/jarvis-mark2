"""Genuine subprocess tool workers for public repository evidence.

No network, external source execution, model API, broker access or credentials.
Queued nodes are planned tasks. Only RUNNING nodes have a live launched PID.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
import fcntl

SCHEMA_VERSION = 1
MAX_PARALLEL = 2
CHILD_TIMEOUT = 15
ROLES = ('LICENSE_CHECK', 'SOURCE_STATIC_REVIEW', 'CANDIDATE_READINESS')
REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
CLEAR_LICENSES = {'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'GPL-3.0', 'GPL-3.0-only', 'GPL-3.0-or-later', 'GPL-2.0', 'GPL-2.0-only', 'GPL-2.0-or-later', 'LGPL-3.0', 'MPL-2.0'}


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def _validate_repo(repo):
    if not isinstance(repo, dict) or not REPO_PATTERN.fullmatch(str(repo.get('repository', ''))):
        raise ValueError('Invalid public repository identity')
    license_id = repo.get('license')
    if license_id is not None and not isinstance(license_id, str):
        raise ValueError('Invalid license metadata')
    if not isinstance(repo.get('files', []), list):
        raise ValueError('Invalid source-file metadata')
    return repo


def _normalized_status(status):
    if not isinstance(status, dict) or not isinstance(status.get('repositories'), list):
        raise ValueError('Cloud status must contain a repository list')
    if len(status['repositories']) > 30: raise ValueError('Repository limit exceeded')
    repositories = []
    for item in status['repositories']:
        _validate_repo(item)
        repositories.append({key: item.get(key) for key in ('repository', 'license', 'commit', 'files', 'error')})
    return {'observed_unix': status.get('observed_unix'), 'repositories': repositories}


def _sources(root, repo):
    """Only matching pinned public source evidence; never execute/import source."""
    folder = Path(root) / 'data' / 'sources'
    expected = {item.get('path'): item.get('sha256') for item in repo.get('files', []) if isinstance(item, dict)}
    found, rejected = [], []
    if folder.is_dir():
        for path in sorted(folder.glob('*.json'))[:512]:
            if path.stat().st_size > 500_000: continue
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if data.get('repository') != repo['repository'] or data.get('commit') != repo.get('commit'): continue
                name, text = data.get('path'), data.get('text')
                if name not in expected or not isinstance(text, str): continue
                digest = hashlib.sha256(text.encode()).hexdigest()
                if expected[name] != digest:
                    rejected.append({'path': name, 'reason': 'SHA256_MISMATCH'}); continue
                found.append({'path': name, 'sha256': digest, 'text': text})
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    return found, rejected, sorted(set(expected) - {x['path'] for x in found})


def evaluate(root, role, repo):
    _validate_repo(repo)
    if role not in ROLES: raise ValueError('Unknown worker role')
    license_id = repo.get('license')
    clear = license_id in CLEAR_LICENSES
    common = {'repository': repo['repository'], 'commit': repo.get('commit'), 'role': role,
              'model_provider': None, 'profitability': 'UNPROVEN', 'broker_commands': 0,
              'external_code_executed': False, 'source_scope': 'SAVED_PUBLIC_EVIDENCE_ONLY'}
    if role == 'LICENSE_CHECK':
        return {**common, 'decision': 'LICENSE_REVIEW_REQUIRED' if clear else 'HOLD_UNKNOWN_LICENSE',
                'license': license_id, 'license_metadata_recognized': clear,
                'distribution_obligations_reviewed': False,
                'notice': 'Metadata recognition is not a legal review or permission certificate.'}
    sources, rejected, missing = _sources(root, repo)
    checks = []
    patterns = {'mentions_grid_or_martingale': r'grid|martingale', 'mentions_order_send': r'OrderSend|CTrade',
                'mentions_dll_import': r'#import\s+["\'][^"\']+\.dll', 'mentions_web_request': r'WebRequest',
                'mentions_stop_loss': r'\bSL\b|stop.?loss', 'mentions_take_profit': r'\bTP\b|take.?profit'}
    for source in sources:
        checks.append({'path': source['path'], 'sha256': source['sha256'],
                       'heuristics': {name: bool(re.search(pattern, source['text'], re.I)) for name, pattern in patterns.items()}})
    scope = {'matched_source_files': len(sources), 'declared_source_files': len(repo.get('files', [])),
             'missing_sources': missing, 'rejected_sources': rejected}
    if role == 'SOURCE_STATIC_REVIEW':
        return {**common, **scope, 'decision': 'MANUAL_SOURCE_REVIEW_REQUIRED' if sources else 'HOLD_NO_MATCHING_SOURCE',
                'files': checks, 'notice': 'Raw text heuristics include comments and do not prove reachable behavior, safety, or edge.'}
    blockers = ['NATIVE_MT5_COMPILE_NOT_VERIFIED', 'SIGNAL_PARITY_NOT_VERIFIED', 'PROFITABILITY_NOT_VERIFIED']
    if not clear: blockers.append('LICENSE_UNCONFIRMED')
    if not sources or missing or rejected: blockers.append('SOURCE_EVIDENCE_INCOMPLETE')
    return {**common, **scope, 'decision': 'NOT_READY_FOR_TRADING', 'blockers': blockers,
            'compile_status': 'NOT_VERIFIED', 'automatic_promotion': False,
            'notice': 'This worker checks evidence readiness, not strategy performance.'}


def _child(root, role):
    try:
        request = json.loads(sys.stdin.read(200_001))
        result = evaluate(root, role, request)
        print(json.dumps({'status': 'COMPLETED', 'result': result}, allow_nan=False))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error': str(error)[:250]}))
        return 1


def read_status(root):
    path = Path(root) / 'data' / 'worker-fleet.json'
    try:
        status=json.loads(path.read_text(encoding='utf-8'))
        if status.get('status')=='RUNNING':
            supervisor=next((n for n in status.get('nodes',[]) if n.get('kind')=='DETERMINISTIC_SUPERVISOR'),None)
            if supervisor and not _alive(supervisor.get('pid')):
                status['status']='INTERRUPTED'
                supervisor['status']='INTERRUPTED'
                for node in status.get('nodes',[]):
                    if node.get('status')=='QUEUED':node['status']='NOT_STARTED'
                    elif node.get('status')=='RUNNING' and (not node.get('pid') or not _alive(node['pid'])):node['status']='INTERRUPTED'
                children=[n for n in status.get('nodes',[]) if n.get('kind')=='DETERMINISTIC_TOOL_WORKER']
                status['counts']={**status.get('counts',{}),**{state.lower():sum(n.get('status')==state for n in children) for state in ('RUNNING','QUEUED','INTERRUPTED','NOT_STARTED')}}
                status['notice']='Supervisor no longer alive. Historical PID records do not imply current activity.'
        return status
    except (OSError, ValueError):
        return {'schema_version': SCHEMA_VERSION, 'status': 'NOT_STARTED', 'nodes': [], 'counts': {},
                'model_provider': None, 'notice': 'No worker fleet has run yet.'}


def run_once(root, cloud_status):
    root = Path(root).resolve(); data = root / 'data'; data.mkdir(parents=True, exist_ok=True)
    lease = (data / 'worker-fleet.run.lock').open('a+')
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close(); return read_status(root)
    try:
        source = _normalized_status(cloud_status)
        run_id = 'fleet-' + uuid.uuid4().hex[:12]
        now = time.time()
        supervisor_id = run_id + '/supervisor'
        nodes = [{'id': supervisor_id, 'parent_id': None, 'name': 'Mark 2 repository supervisor',
                  'kind': 'DETERMINISTIC_SUPERVISOR', 'status': 'RUNNING', 'repository': None,
                  'task': 'Coordinate bounded public-evidence subprocess workers', 'started_unix': now,
                  'completed_unix': None, 'pid': os.getpid(), 'result': None, 'model_provider': None}]
        jobs = []
        for index, repo in enumerate(source['repositories']):
            group_id = f'{run_id}/repo-{index+1}'
            nodes.append({'id': group_id, 'parent_id': supervisor_id, 'name': repo['repository'],
                          'kind': 'REPOSITORY_TASK_GROUP', 'status': 'QUEUED', 'repository': repo['repository'],
                          'task': 'Three source-evidence tasks; grouping only, not another process',
                          'started_unix': None, 'completed_unix': None, 'pid': None, 'result': None, 'model_provider': None})
            for role in ROLES:
                node = {'id': f'{group_id}/{role.lower()}', 'parent_id': group_id,
                        'name': role.replace('_', ' ').title(), 'kind': 'DETERMINISTIC_TOOL_WORKER',
                        'status': 'QUEUED', 'repository': repo['repository'], 'task': role,
                        'started_unix': None, 'completed_unix': None, 'pid': None, 'result': None,
                        'model_provider': None, 'role_pool': role}
                nodes.append(node); jobs.append((node, repo))
        fleet = {'schema_version': SCHEMA_VERSION, 'run_id': run_id, 'status': 'RUNNING',
                 'started_unix': now, 'completed_unix': None, 'source_observed_unix': source['observed_unix'],
                 'nodes': nodes, 'counts': {}, 'max_parallel_subprocesses': MAX_PARALLEL,
                 'child_timeout_seconds': CHILD_TIMEOUT, 'model_provider': None,
                 'notice': 'Actual deterministic software workers, not child LLMs owned by Claude, Grok or other providers. QUEUED means planned; PID identifies an actually launched process.'}
        state_lock = threading.Lock()
        groups = {n['id']: n for n in nodes if n['kind'] == 'REPOSITORY_TASK_GROUP'}
        def persist():
            children = [n for n in nodes if n['kind'] == 'DETERMINISTIC_TOOL_WORKER']
            fleet['counts'] = {s.lower(): sum(n['status'] == s for n in children) for s in ('QUEUED','RUNNING','COMPLETED','FAILED','TIMED_OUT')}
            fleet['counts'].update(repositories=len(groups), workers=len(children), launched=sum(n['started_unix'] is not None for n in children))
            for group_id, group in groups.items():
                members = [n for n in children if n['parent_id'] == group_id]
                begun = [n['started_unix'] for n in members if n['started_unix'] is not None]
                group['started_unix'] = min(begun) if begun else None
                if all(n['status'] in ('COMPLETED','FAILED','TIMED_OUT') for n in members):
                    group['status'] = 'COMPLETED' if all(n['status'] == 'COMPLETED' for n in members) else 'FAILED'
                    group['completed_unix'] = max(n['completed_unix'] for n in members)
                elif begun: group['status'] = 'RUNNING'
            atomic_json(data/'worker-fleet.json', fleet)
        with state_lock: persist()
        def perform(node, repo):
            process = None
            try:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--child', node['task'], '--root', str(root)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    cwd=str(root), env={k: v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','WINDIR')})
                with state_lock:
                    node.update(status='RUNNING', pid=process.pid, started_unix=time.time()); persist()
                stdout, stderr = process.communicate(json.dumps(repo), timeout=CHILD_TIMEOUT)
                message = json.loads(stdout)
                with state_lock:
                    node.update(status='COMPLETED' if process.returncode == 0 and message.get('status') == 'COMPLETED' else 'FAILED',
                                completed_unix=time.time(), result=message.get('result'), error=message.get('error'))
                    persist()
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate()
                with state_lock: node.update(status='TIMED_OUT', completed_unix=time.time(), error='Child exceeded bounded runtime'); persist()
            except Exception as error:
                if process and process.poll() is None: process.kill(); process.communicate()
                with state_lock: node.update(status='FAILED', completed_unix=time.time(), error=str(error)[:250]); persist()
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            futures=[pool.submit(perform,node,repo) for node,repo in jobs]
            for future in futures: future.result()
        fleet['completed_unix']=time.time()
        fleet['status']='COMPLETED' if not (fleet['counts']['failed'] or fleet['counts']['timed_out']) else 'COMPLETED_WITH_ERRORS'
        nodes[0].update(status=fleet['status'], completed_unix=fleet['completed_unix'])
        with state_lock: persist()
        return fleet
    finally:
        fcntl.flock(lease, fcntl.LOCK_UN); lease.close()


def _alive(pid):
    try: os.kill(int(pid), 0); return True
    except (OSError, TypeError, ValueError): return False


def kickoff(root, cloud_status):
    """Start a real supervisor process without blocking the display request.

    Returns {status: STARTED|ALREADY_RUNNING|INVALID_INPUT, pid, run_id?}.
    read_status(root) exposes actual progress. No network calls or model APIs.
    """
    root=Path(root).resolve(); data=root/'data'; data.mkdir(parents=True,exist_ok=True)
    try: source=_normalized_status(cloud_status)
    except ValueError as error: return {'status':'INVALID_INPUT','error':str(error),'pid':None}
    with (data/'worker-fleet.launch.lock').open('a+') as launch:
        fcntl.flock(launch,fcntl.LOCK_EX)
        pid_path=data/'worker-fleet-supervisor.pid'
        try: old_pid=int(pid_path.read_text())
        except (OSError,ValueError): old_pid=None
        if old_pid and _alive(old_pid): return {'status':'ALREADY_RUNNING','pid':old_pid}
        input_path=data/'worker-fleet-input.json'; atomic_json(input_path, source)
        log=(data/'worker-fleet-supervisor.log').open('a')
        try:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--once','--root',str(root),'--input',str(input_path)],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,cwd=str(root),
                env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT','WINDIR')})
            pid_path.write_text(str(process.pid))
        finally: log.close()
        return {'status':'STARTED','pid':process.pid}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parent))
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--input')
    parser.add_argument('--child',choices=ROLES)
    args=parser.parse_args()
    if args.child:return _child(args.root,args.child)
    root=Path(args.root)
    source=json.loads(Path(args.input).read_text()) if args.input else json.loads((root/'data/office-cloud-evidence.json').read_text())['cloud']
    try:
        result=run_once(root,source)
        print(json.dumps({'run_id':result.get('run_id'),'status':result['status'],'counts':result['counts']}))
        return 0 if result['status']=='COMPLETED' else 1
    finally:
        pid_path=root/'data/worker-fleet-supervisor.pid'
        try:
            if int(pid_path.read_text())==os.getpid():pid_path.unlink()
        except (OSError,ValueError):pass

if __name__=='__main__':raise SystemExit(main())
