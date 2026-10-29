"""Low-load public-source crawler. Reads pinned GitHub source; never executes it."""
import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from worker_fleet import atomic_json

class Crawler:
    def __init__(self,root,hub,cloud_provider,kickoff,max_requests=None,pause_seconds=3,stop_when_idle=False,max_seconds=None):
        self.root=Path(root);self.hub=hub;self.cloud_provider=cloud_provider;self.kickoff=kickoff
        self.state={'status':'STARTING','visited':0,'failed':0,'current_url':None,'queue_remaining':0,'recent':[],'external_code_executed':False}
        self.seen=set();self.thread=threading.Thread(target=self.run,daemon=True)
        self.indexed={};self.extra=[];self.discovered={}
        self.wake=threading.Event()
        self.max_requests=max_requests;self.pause_seconds=pause_seconds;self.stop_when_idle=stop_when_idle
        self.deadline=time.monotonic()+max_seconds if max_seconds else None
        if max_requests is None:
            try:
                previous=json.loads((self.root/'data/crawler-status.json').read_text())
                self.state.update(previous,status='STARTING',current_url=None)
            except (OSError,ValueError):pass
            for file in list((self.root/'data/sources').glob('*.json'))[:512]:
                try:
                    item=json.loads(file.read_text());key=(item['repository'],item['commit'],item['path'])
                    if all(isinstance(x,str) for x in key):self.seen.add(key)
                except (OSError,ValueError,KeyError,TypeError):pass
            for item in self.state.get('recent',[]):
                if item.get('result')=='FETCH_FAILED':
                    parts=urllib.parse.urlparse(item.get('url','')).path.strip('/').split('/',3)
                    if len(parts)==4:self.seen.add((parts[0]+'/'+parts[1],parts[2],urllib.parse.unquote(parts[3])))

    def bounded_done(self):
        return (self.max_requests is not None and self.state['visited']+self.state['failed']>=self.max_requests) or (self.deadline is not None and time.monotonic()>=self.deadline)

    def request_scan(self):
        self.indexed.clear();self.wake.set()
        return {'status':'SOURCE_VERSION_SCAN_REQUESTED','already_running':self.thread.is_alive()}

    def expand_frontier(self):
        """Read public Git trees without checkout, submodules, hooks or source execution."""
        cloud=self.cloud_provider() or {}
        git=shutil.which('git')
        if not git:
            self.state.update(status='GIT_DISCOVERY_UNAVAILABLE');self.persist();return
        base=self.root/'data/crawl-index';base.mkdir(exist_ok=True)
        for repo in cloud.get('repositories',[]):
            if self.bounded_done():return
            name=repo.get('repository','')
            if not re.fullmatch(r'[\w.-]+/[\w.-]+',name) or time.time()-self.indexed.get(name,0)<900:continue
            self.indexed[name]=time.time();self.state.update(status='DISCOVERING_PUBLIC_GIT_TREE',current_url='https://github.com/'+name,current_repository=name);self.persist()
            folder=base/name.replace('/','--')
            common=[git,'-c','credential.helper=','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false']
            env={'PATH':'/usr/bin:/bin','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'}
            try:
                if not folder.exists():
                    subprocess.run(common+['clone','--bare','--depth=1','--filter=blob:none','https://github.com/'+name+'.git',str(folder)],env=env,capture_output=True,timeout=25,check=True)
                else:
                    subprocess.run(common+['--git-dir',str(folder),'fetch','--depth=1','origin','HEAD'],env=env,capture_output=True,timeout=25,check=True)
                ref='FETCH_HEAD' if (folder/'FETCH_HEAD').exists() else 'HEAD'
                sha=subprocess.run(common+['--git-dir',str(folder),'rev-parse',ref],env=env,capture_output=True,text=True,timeout=5,check=True).stdout.strip()
                paths=subprocess.run(common+['--git-dir',str(folder),'ls-tree','-r','--name-only',sha],env=env,capture_output=True,text=True,timeout=5,check=True).stdout.splitlines()
                paths=[p for p in paths if p.lower().endswith(('.mq5','.mqh')) and not re.search(r'(^|/)(tests?|examples?)(/|$)',p,re.I)]
                paths.sort(key=lambda p:('expert' not in p.lower(),not p.lower().endswith('.mq5'),p))
                for path in paths[:8]:
                    key=(name,sha,path)
                    if key not in self.seen and not any(x[0]==key for x in self.extra):self.extra.append((key,{**repo,'commit':sha},{'path':path}))
                self.hub.route('CRAWLER','CONTEXT','FRONTIER_EXPANDED',{'repository':name,'commit':sha,'source_paths_found':len(paths),'bounded_source_queue':min(8,len(paths)),'method':'public Git tree; no checkout or source execution'},'LIVE_PUBLIC_REPOSITORY_DISCOVERY')
            except Exception as error:
                self.hub.route('CRAWLER','CONTEXT','DISCOVERY_FAILED',{'repository':name,'error':type(error).__name__,'retry_after_seconds':900},'LIVE_PUBLIC_REPOSITORY_DISCOVERY')

    def worker_input(self):
        cloud=json.loads(json.dumps(self.cloud_provider() or {}))
        for repo in cloud.get('repositories',[]):
            if repo.get('repository') in self.discovered:
                update=self.discovered[repo['repository']]
                same_commit=repo.get('commit')==update['commit']
                if not same_commit:repo['license']=None
                merged={item['path']:item for item in repo.get('files',[]) if isinstance(item,dict) and 'path' in item} if same_commit else {}
                merged.update(update['files'])
                repo['commit']=update['commit'];repo['files']=list(merged.values())
        cloud['observed_unix']=time.time();return cloud

    def persist(self):
        self.state['observed_unix']=time.time();atomic_json(self.root/'data/crawler-status.json',self.state)

    def frontier(self):
        cloud=self.cloud_provider() or {};jobs=[]
        for repo in cloud.get('repositories',[]):
            name=repo.get('repository','');commit=repo.get('commit','')
            if not re.fullmatch(r'[\w.-]+/[\w.-]+',name) or not re.fullmatch(r'[0-9a-f]{40}',commit):continue
            for item in repo.get('files',[]):
                path=item.get('path','')
                if not isinstance(path,str) or not path.lower().endswith(('.mq5','.mqh')) or '..' in path.split('/'):continue
                key=(name,commit,path)
                if key not in self.seen:jobs.append((key,repo,item))
        jobs.extend(x for x in self.extra if x[0] not in self.seen)
        # Stable de-duplication prevents repeated requests for the same pinned path.
        return list({job[0]:job for job in jobs}.values())

    def run(self):
        while True:
            if self.bounded_done():
                self.state.update(status='BOUNDED_CRAWL_COMPLETE',current_url=None);self.persist();return
            jobs=self.frontier();self.state['queue_remaining']=len(jobs)
            if not jobs:
                self.expand_frontier();jobs=self.frontier();self.state['queue_remaining']=len(jobs)
                if not jobs:
                    self.state.update(status='WATCHING_FOR_SOURCE_UPDATES',current_url=None);self.persist()
                    if self.stop_when_idle:return
                    self.wake.wait(30);self.wake.clear();continue
            batch=0
            for key,repo,item in jobs:
                if self.bounded_done():break
                name,commit,path=key
                url='https://raw.githubusercontent.com/'+name+'/'+commit+'/'+urllib.parse.quote(path,safe='/')
                self.state.update(status='FETCHING_PUBLIC_SOURCE',current_url=url,current_repository=name);self.persist()
                self.hub.route('CRAWLER','CONTEXT','FETCH_STARTED',{'url':url,'repository':name,'commit':commit,'path':path},'LIVE_PUBLIC_SOURCE_CRAWL')
                try:
                    request=urllib.request.Request(url,headers={'User-Agent':'Jarvis-Spider-Source-Review/1.0'})
                    with urllib.request.urlopen(request,timeout=15) as response:raw=response.read(150_001)
                    if len(raw)>150_000:raise ValueError('Source size limit')
                    text=raw.decode('utf-8',errors='replace');digest=hashlib.sha256(text.encode()).hexdigest()
                    if item.get('sha256') and digest!=item['sha256']:raise ValueError('Pinned source checksum mismatch')
                    # Match the worker's inert JSON evidence format.
                    atomic_json(self.root/'data/sources'/(digest+'.json'),{'repository':name,'commit':commit,'path':path,'text':text,'analysis':{'sha256':digest}})
                    record={'url':url,'repository':name,'path':path,'sha256':digest,'bytes':len(raw),'result':'SOURCE_SAVED','received_unix':time.time()}
                    self.state['visited']+=1;self.seen.add(key);batch+=1
                    entry=self.discovered.setdefault(name,{'commit':commit,'files':{}})
                    if entry['commit']!=commit:entry.update(commit=commit,files={})
                    entry['files'][path]={'path':path,'sha256':digest}
                    self.hub.route('CRAWLER','CONTEXT','SOURCE_FETCHED',record,'LIVE_PUBLIC_SOURCE_CRAWL')
                except Exception as error:
                    record={'url':url,'repository':name,'path':path,'result':'FETCH_FAILED','error':str(error)[:200],'received_unix':time.time()}
                    self.state['failed']+=1
                    # Back off this URL for this process; retry after a fresh crawler start.
                    self.seen.add(key);self.hub.route('CRAWLER','CONTEXT','SOURCE_FETCH_FAILED',record,'LIVE_PUBLIC_SOURCE_CRAWL')
                self.state['recent']=([record]+self.state['recent'])[:20]
                self.state['queue_remaining']=max(0,self.state['queue_remaining']-1);self.state['status']=record['result'];self.persist()
                if batch and batch%4==0:self.hub.launch_workers(self.kickoff,self.worker_input())
                if self.pause_seconds:time.sleep(self.pause_seconds)
            if batch:self.hub.launch_workers(self.kickoff,self.worker_input())

def bounded_crawl(root,status):
    from spider_hub import SpiderHub
    hub=SpiderHub(root)
    crawler=Crawler(root,hub,lambda:status,
                    lambda root,cloud:{'status':'DEFERRED_TO_CLOUD_SUPERVISOR','pid':None},
                    max_requests=12,pause_seconds=0,stop_when_idle=True,max_seconds=90)
    previous_path=Path(root)/'data/cloud-crawler.json'
    try:
        previous=json.loads(previous_path.read_text())
        for key in previous.get('seen_sources',[]):
            if isinstance(key,list) and len(key)==3 and all(isinstance(x,str) for x in key):crawler.seen.add(tuple(key))
        # Upgrade the first saved batch to a persistent frontier without refetching it.
        for item in previous.get('recent',[]):
            parts=urllib.parse.urlparse(item.get('url','')).path.strip('/').split('/',3)
            if len(parts)==4:crawler.seen.add((parts[0]+'/'+parts[1],parts[2],urllib.parse.unquote(parts[3])))
    except (OSError,ValueError,TypeError):pass
    crawler.run()
    cursor={**crawler.state,'seen_sources':[list(key) for key in sorted(crawler.seen)[-2000:]]}
    crawler.state['frontier_total_seen']=len(crawler.seen)
    atomic_json(Path(root)/'data/cloud-crawler.json',cursor)
    return {'state':crawler.state,'source_snapshot':crawler.worker_input()}
