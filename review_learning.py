"""Durable lessons from evidence checks; no model training or auto-deployment."""
import hashlib
import json
import time
from pathlib import Path

def review(root, fleet):
    root=Path(root);path=root/'data/review-lessons.json'
    try:history=json.loads(path.read_text())
    except (OSError,ValueError):history={'processed_runs':[],'findings':{}}
    run=fleet.get('run_id')
    if not run or fleet.get('status') not in ('COMPLETED','COMPLETED_WITH_ERRORS') or run in history['processed_runs']:return history
    now=time.time();new=0;seen_in_review=set()
    for node in fleet.get('nodes',[]):
        result=node.get('result') or {};repo=node.get('repository')
        if node.get('kind')!='DETERMINISTIC_TOOL_WORKER' or not repo:continue
        rules=list(result.get('blockers') or [])
        if result.get('decision')=='HOLD_UNKNOWN_LICENSE':rules.append('LICENSE_UNCONFIRMED')
        for source in result.get('files',[]):
            for key,value in source.get('heuristics',{}).items():
                if value and key in ('mentions_grid_or_martingale','mentions_dll_import','mentions_web_request'):
                    rules.append('REVIEW_'+key.upper())
        for rule in sorted(set(rules)):
            key=hashlib.sha256((repo+'|'+str(result.get('commit'))+'|'+rule).encode()).hexdigest()[:20]
            if key in seen_in_review:continue
            seen_in_review.add(key)
            item=history['findings'].get(key)
            if not item:
                new+=1;item={'id':key,'repository':repo,'commit':result.get('commit'),'rule':rule,'first_seen_unix':now,'reviews_seen':0,'state':'OPEN','evidence_kind':'STATIC_CHECK_NOT_PROFIT_TEST'}
                history['findings'][key]=item
            item.update(last_seen_unix=now,last_run_id=run,reviews_seen=item['reviews_seen']+1)
    history['processed_runs']=(history['processed_runs']+[run])[-100:]
    history.update(last_review_unix=now,last_run_id=run,new_findings_this_review=new,model_weights_trained=False,
                   automatic_code_changes=False,automatic_trading_promotion=False,
                   next_actions=['Obtain missing source/license evidence','Compile isolated MT5 candidate when scheduled for evaluation','Verify signal parity before strategy promotion'])
    path.parent.mkdir(exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(history,indent=2));temp.replace(path)
    return history
