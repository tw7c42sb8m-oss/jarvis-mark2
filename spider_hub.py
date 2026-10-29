"""Local, read-only research message router. No model or broker commands."""
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

class SpiderHub:
    def __init__(self, root):
        self.root=Path(root);self.lock=threading.Lock()
        self.path=self.root/'data/spider.sqlite3';self.path.parent.mkdir(exist_ok=True)
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS packets(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, source TEXT, target TEXT, kind TEXT, received REAL, payload TEXT, origin TEXT); CREATE TABLE IF NOT EXISTS latest(source TEXT PRIMARY KEY,fingerprint TEXT);')

    def connect(self):
        db=sqlite3.connect(str(self.path));db.row_factory=sqlite3.Row;return db

    def route(self,source,target,kind,payload,origin):
        body=json.dumps(payload,sort_keys=True,ensure_ascii=False,allow_nan=False)
        if len(body)>100_000:raise ValueError('Packet too large')
        digest=hashlib.sha256((source+'|'+target+'|'+kind+'|'+body).encode()).hexdigest()
        with self.lock,self.connect() as db:
            previous=db.execute('SELECT fingerprint FROM latest WHERE source=?',(source,)).fetchone()
            if previous and previous[0]==digest:return
            # Fingerprint dedup is durable; timestamps mean hub receipt, not model activity.
            db.execute('INSERT OR IGNORE INTO packets(fingerprint,source,target,kind,received,payload,origin) VALUES(?,?,?,?,?,?,?)',(digest,source,target,kind,time.time(),body,origin))
            db.execute('INSERT OR REPLACE INTO latest VALUES(?,?)',(source,digest))
            db.execute('DELETE FROM packets WHERE id < (SELECT COALESCE(MAX(id),0)-2000 FROM packets)')

    def ingest(self, office):
        team_path=self.root/'team.json'
        if team_path.is_file():
            team=json.loads(team_path.read_text())
            reviews={
                'Claude': 'Reuse small pinned 3MACD signal functions; remove EAUtils execution coupling.',
                'Kimi': 'Design reproducible comparisons; verify additional source licenses.',
                'Grok': 'Distinguish input defaults from report settings; grid is not necessarily martingale.',
                'DeepSeek': 'Require complete buffers; preserve reversal convention; indexing correction acknowledged.',
                'Gemini': 'Prefer a minimal signal adapter; do not infer profitability from source popularity.',
                'Perplexity': 'Discover primary repositories; separate strategy EAs from position-sizing tools.'}
            for name in team.get('external_web_reviews_received',[]):
                if name in reviews:self.route(name.upper(),'CONTEXT','ARCHIVED_REVIEW',{'review_date':team['consulted_on'],'summary':reviews[name],'provenance':'AI-TEAM.md / recorded web consultation','direct_model_connection':False},'LOCAL_REVIEW_ARCHIVE')
        cloud=office.get('cloud')
        if cloud:
            self.route('GITHUB','CONTEXT','CLOUD_RESEARCH',{'observed_unix':cloud.get('observed_unix'),'status':cloud.get('status'),'repositories':[{'repository':x.get('repository'),'files_screened':len(x.get('files',[]))} for x in cloud.get('repositories',[])],'candidates':[{'id':x.get('id'),'sha256':x.get('sha256'),'compile_status':x.get('compile_status')} for x in cloud.get('generated_candidates',[])],'origin':'public GitHub data/status.json'},'PUBLIC_CLOUD_RECORD')
        m=office.get('mark1',{})
        # No broker account ID, password, order API or action is accepted.
        self.route('QWEN','OFFICE','MONITOR_TELEMETRY',{'fresh':bool(m.get('fresh')),'ai_fresh':bool(m.get('ai_fresh')),'status':m.get('ai_status'),'observed_utc':m.get('observed_utc'),'positions':m.get('positions'),'demo_equity':m.get('equity'),'currency':m.get('currency')},'READ_ONLY_MARK1_MONITOR')
        fleet=office.get('worker_fleet') or {}
        if fleet.get('run_id'):
            self.route('WORKER_FLEET','CONTEXT','WORKER_RESULTS',{'run_id':fleet['run_id'],'status':fleet['status'],'counts':fleet.get('counts'), 'workers':[{'id':n['id'],'repository':n.get('repository'),'task':n.get('task'),'pid':n.get('pid'),'status':n['status'],'decision':(n.get('result') or {}).get('decision')} for n in fleet.get('nodes',[]) if n.get('kind')=='DETERMINISTIC_TOOL_WORKER']},'ACTUAL_SUBPROCESS_RESULTS')
        with self.connect() as db:
            rows=db.execute('SELECT p.* FROM latest l JOIN packets p ON p.fingerprint=l.fingerprint WHERE p.target="CONTEXT" ORDER BY p.source').fetchall()
        context={'purpose':'Research evidence for office inspection; not a model execution request','inputs':[{'packet_id':r['id'],'source':r['source'],'fingerprint':r['fingerprint'],'payload':json.loads(r['payload'])} for r in rows]}
        file=self.root/'data/spider-context.json'
        with self.lock:
            temp=file.with_suffix('.tmp');temp.write_text(json.dumps(context,indent=2));temp.replace(file)
        self.route('CONTEXT','OFFICE','CONTEXT_BUNDLE',context,'SPIDER_COMPILED_CONTEXT')

    def snapshot(self):
        with self.connect() as db:
            count=db.execute('SELECT COUNT(*) FROM packets').fetchone()[0]
            rows=db.execute('SELECT * FROM packets ORDER BY id DESC LIMIT 40').fetchall()
        packets=[]
        for row in rows:
            item=dict(row);item['payload']=json.loads(item['payload']);item['via']='SPIDER';packets.append(item)
        return {'mode':'LOCAL_EVIDENCE_ROUTER','packets':packets,'retained_packets':count,
                'external_model_api_connections':0,'broker_commands':0,
                'notice':'AI edges deliver saved reviews. Qwen edge carries read-only monitor data. No AI-to-AI API exchange is configured.'}

    def launch_workers(self, kickoff, cloud):
        result=kickoff(self.root,cloud)
        self.route('SPIDER_SCHEDULER','WORKER_FLEET','DISPATCH_CHILDREN',{'status':result['status'],'supervisor_pid':result.get('pid'),'source_observed_unix':(cloud or {}).get('observed_unix')},'ACTUAL_WORKER_DISPATCH')
        return result

def cloud_cycle(root,status):
    """Spider's cloud orchestration: real subprocess tasks, then durable lessons."""
    from worker_fleet import run_once
    from review_learning import review
    hub=SpiderHub(root)
    hub.route('GITHUB','WORKER_FLEET','DISPATCH_CHILDREN',{'repositories':[x['repository'] for x in status.get('repositories',[])],'observed_unix':status.get('observed_unix')},'CLOUD_RESEARCH_CYCLE')
    fleet=run_once(root,status)
    lessons=review(root,fleet)
    hub.route('WORKER_FLEET','CONTEXT','WORKER_RESULTS',{'run_id':fleet.get('run_id'),'status':fleet.get('status'),'counts':fleet.get('counts')},'ACTUAL_CLOUD_SUBPROCESSES')
    hub.route('CONTEXT','OFFICE','REVIEW_LESSONS',{'new_findings':lessons.get('new_findings_this_review',0),'open_findings':len(lessons.get('findings',{})),'model_training':False,'automatic_trading_promotion':False},'PERSISTED_REVIEW_LESSONS')
    return {'identity':'JARVIS MARK 2 / SPIDER','fleet_run_id':fleet.get('run_id'),'fleet_status':fleet['status'],'counts':fleet.get('counts'),
            'new_findings':lessons.get('new_findings_this_review',0),'open_findings':len(lessons.get('findings',{})),
            'model_children':False,'worker_type':'DETERMINISTIC_TOOL_WORKER','external_ai_apis':0}
