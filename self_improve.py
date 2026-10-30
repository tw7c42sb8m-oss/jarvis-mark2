"""Bounded research self-improvement. Only two reviewed repair recipes may run.
No arbitrary model code execution, broker commands, paid APIs or self-modifying runner.
C++ probes test isolated numeric functions, never an EA or native MT5 runtime.
"""
import sys
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2));temp.replace(path)

def function(source,name):
    match=re.search(r'\bdouble\s+'+name+r'\([^)]*\)\s*\{',source)
    if not match:raise ValueError('Expected numeric function missing')
    start=match.start();end=match.end();depth=1
    while end<len(source) and depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    if depth:raise ValueError('Unbalanced function')
    return source[start:end]

RECIPES=('FINITE_RISK_INPUTS','AVERAGE_ARRAY_BOUNDS')

def repair(source,recipe):
    name='RiskLots' if recipe=='FINITE_RISK_INPUTS' else 'Avg'
    original=function(source,name)
    if recipe=='FINITE_RISK_INPUTS':
        guard='\n   if(!MathIsValidNumber(budget) || !MathIsValidNumber(loss) || !MathIsValidNumber(minimum) || !MathIsValidNumber(step) || !MathIsValidNumber(maximum))return 0;'
        if 'MathIsValidNumber' in original:return None
        changed=original.replace('{','{'+guard,1)
    elif recipe=='AVERAGE_ARRAY_BOUNDS':
        if 'end>ArraySize(r)' in original:return None
        changed=original.replace('if(end<count)return 0;','if(count<=0 || end<count || end>ArraySize(r))return 0;')
        if changed==original:raise ValueError('Unknown average implementation')
    else:raise ValueError('Recipe is not approved')
    candidate=source.replace(original,changed,1)
    # Only the selected pure function can change. All order/risk policy stays identical.
    assert candidate.replace(changed,original,1)==source
    if '!MQLInfoInteger(MQL_TESTER)' not in source:raise ValueError('Missing tester-only guard')
    return candidate


def probe(source,recipe):
    compiler=shutil.which('c++') or shutil.which('g++') or shutil.which('clang++')
    if not compiler:return {'status':'UNAVAILABLE','passed':False,'checks':0}
    name='RiskLots' if recipe=='FINITE_RISK_INPUTS' else 'Avg'
    body=function(source,name)
    prelude='''#include <cmath>\n#include <algorithm>\n#include <vector>\n#include <limits>\n#include <iostream>\nusing std::isfinite;\ndouble MathMin(double a,double b){return std::min(a,b);}\ndouble MathFloor(double x){return std::floor(x);}\ndouble NormalizeDouble(double x,int n){double p=std::pow(10.,n);return std::round(x*p)/p;}\nbool MathIsValidNumber(double x){return std::isfinite(x);}\nstruct MqlRates{double close;};\nint ArraySize(const std::vector<MqlRates>&r){return (int)r.size();}\n'''
    if name=='RiskLots':
        main='''int main(){int failed=0,checks=0;double values[]={10.,100.,.01,.01,1.};double bad[]={NAN,INFINITY,-INFINITY};for(int i=0;i<5;i++)for(double v:bad){double a[5];std::copy(values,values+5,a);a[i]=v;double x=RiskLots(a[0],a[1],a[2],a[3],a[4]);checks++;if(x!=0.)failed++;}for(int b=1;b<=120;b++)for(double step:{.01,.1,.25}){double budget=b*.37,loss=42.,minimum=step,maximum=1.7;double x=RiskLots(budget,loss,minimum,step,maximum);checks++;if(!std::isfinite(x)||x<0||x>maximum+1e-8||x*loss>budget+1e-8||(x>0&&std::abs((x-minimum)/step-std::round((x-minimum)/step))>1e-6))failed++;}std::cout<<checks<<" "<<failed;return failed?1:0;}'''
    else:
        body=body.replace('const MqlRates &r[]','const std::vector<MqlRates>& r')
        # Instrument reads: the unchecked baseline must be rejected before execution.
        if 'end>ArraySize(r)' not in body:return {'status':'BOUNDS_GUARD_MISSING','passed':False,'checks':3}
        main='''int main(){int failed=0,checks=0;std::vector<MqlRates>r={{1.},{3.},{5.}};for(auto q:std::vector<std::pair<int,int>>{{4,2},{2,0},{-1,1},{2,-1}}){checks++;if(Avg(r,q.first,q.second)!=0)failed++;}checks++;if(Avg(r,3,3)!=3.)failed++;checks++;if(Avg(r,3,2)!=4.)failed++;std::cout<<checks<<" "<<failed;return failed?1:0;}'''
    with tempfile.TemporaryDirectory(prefix='mark2-numeric-') as tmp:
        path=Path(tmp);(path/'probe.cpp').write_text(prelude+body+'\n'+main)
        sdk=['-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk'] if sys.platform=='darwin' and Path('/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk').exists() else []
        built=subprocess.run([compiler,*sdk,'-std=c++17','-O0',str(path/'probe.cpp'),'-o',str(path/'probe')],capture_output=True,text=True,timeout=25)
        if built.returncode:return {'status':'HOST_COMPILE_FAILED','passed':False,'checks':0,'error':built.stderr[:500]}
        ran=subprocess.run([str(path/'probe')],capture_output=True,text=True,timeout=5)
        parts=ran.stdout.split();checks=int(parts[0]) if parts else 0
        return {'status':'HOST_NUMERIC_PROBE_PASS' if ran.returncode==0 else 'HOST_NUMERIC_PROBE_FAIL','passed':ran.returncode==0 and checks>0,'checks':checks,'failures':int(parts[1]) if len(parts)>1 else None,'scope':'C++ compatibility probe of extracted pure function; not native MQL5 validation'}


def run_cycle(root,status,lessons=None):
    root=Path(root);out=root/'generated/improvements';ledger=out/'progress.json'
    try:history=json.loads(ledger.read_text())
    except (OSError,ValueError):history={'attempts':[]}
    # Real source evidence changes the research-priority queue each cycle.
    sources=[]
    for repo in status.get('repositories',[]):
        sources.append({'repository':repo['repository'],'source_files':len(repo.get('files',[])),'license':repo.get('license'),'next_action':'REVIEW_LICENSE' if not repo.get('license') or repo.get('license') in ('NOASSERTION','UNKNOWN') else 'REVIEW_SOURCE_AND_NATIVE_VALIDATION'})
    write(out/'research-priorities.json',sources)
    candidates=status.get('generated_candidates') or []
    selected=None
    for entry in candidates:
        name=entry.get('id','')
        if not re.fullmatch(r'Mark2_Trend_\d+_\d+',name):continue
        file=root/'generated'/(name+'.mq5')
        if not file.exists():continue
        source=file.read_text();base=sha(source)
        if entry.get('sha256')!=base:continue
        for recipe in RECIPES:
            key=sha(base+'|'+recipe)[:20]
            if any(a['id']==key for a in history['attempts']):continue
            selected=(name,source,base,recipe,key);break
        if selected:break
    attempt=None
    if selected:
        name,source,base,recipe,key=selected
        attempt={'id':key,'parent':name,'parent_sha256':base,'recipe':recipe,'observed_at':datetime.now(timezone.utc).isoformat(),'native_compile':'NOT_RUN','trading_deployed':False}
        try:
            candidate=repair(source,recipe)
            if candidate is None:attempt['decision']='NO_CHANGE_NEEDED'
            else:
                before=probe(source,recipe);after=probe(candidate,recipe)
                attempt.update(before=before,after=after,candidate_sha256=sha(candidate))
                if not before['passed'] and after['passed']:
                    target=out/(key+'.mq5');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(candidate)
                    attempt.update(decision='ACCEPTED_RESEARCH_CANDIDATE',artifact=str(target.relative_to(root)))
                else:attempt['decision']='REJECTED_NO_VERIFIED_IMPROVEMENT'
        except Exception as e:attempt.update(decision='REJECTED_ERROR',error=str(e)[:250])
        history['attempts'].append(attempt)
    history.update(status='CYCLE_COMPLETE' if attempt else 'WAITING_FOR_NEW_EVIDENCE',mode='BOUNDED_RULE_BASED_RESEARCH_IMPROVEMENT',latest=attempt or history.get('latest'),accepted=sum(a['decision']=='ACCEPTED_RESEARCH_CANDIDATE' for a in history['attempts']),rejected=sum(a['decision'].startswith('REJECTED') for a in history['attempts']),paid_api_calls=0,trading_deployed=False,native_validation='PENDING',automatic_runner_rewriting=False,notice='One approved repair per cloud cycle; accepted means host numeric/source improvement only, not profitable or native MT5 tested.')
    write(ledger,history)
    return history
