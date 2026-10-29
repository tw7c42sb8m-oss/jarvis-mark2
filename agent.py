"""MARK 2: independent, zero-dependency EA source research worker.

Reads public GitHub metadata and source as data only. No broker interface,
remote-code execution, purchases, account creation, or credentials required.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
QUERIES = ['expert advisor language:MQL5', 'scalping language:MQL5']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def api(route):
    request = urllib.request.Request('https://api.github.com/' + route,
        headers={'User-Agent': 'Jarvis-Mark2-EA-Research', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('Response size limit')
    return json.loads(body)


def inspect_source(text):
    # Heuristics are review hints, never a safety certificate or profit estimate.
    checks = {
        'mentions_stop_loss': bool(re.search(r'\b(sl|stoploss|stop_loss)\b', text, re.I)),
        'mentions_take_profit': bool(re.search(r'\b(tp|takeprofit|take_profit)\b', text, re.I)),
        'uses_dll_import': bool(re.search(r'#import\s+["\'][^"\']+\.dll', text, re.I)),
        'uses_web_request': 'WebRequest' in text,
        'mentions_martingale_or_grid': bool(re.search(r'martingale|grid|lotmultiplier', text, re.I)),
        'mentions_order_execution': bool(re.search(r'OrderSend|CTrade|\.Buy\(|\.Sell\(', text)),
    }
    return {'sha256': hashlib.sha256(text.encode()).hexdigest(), 'checks': checks,
            'assessment': 'MANUAL_CODE_REVIEW_REQUIRED', 'profitability': 'UNPROVEN'}


def build_candidates():
    template_path = ROOT / 'templates' / 'JarvisTesterCore.mqh'
    if not template_path.is_file():
        template_path = ROOT / 'JarvisTesterCore.mqh'
    template = template_path.read_text()
    template = template.replace('input int PollSeconds=10;', 'input int PollSeconds=10;\ninput double TargetEquity=0;')
    template = template.replace('AccountInfoDouble(ACCOUNT_BALANCE)>=2000', 'TargetEquity>0 && AccountInfoDouble(ACCOUNT_BALANCE)>=TargetEquity')
    template = template.replace('JARVIS_PRIME_Tests', 'JARVIS_MARK2_Tests')
    output = ROOT / 'generated'
    output.mkdir(exist_ok=True)
    variants = []
    for fast, slow in [(5, 20), (10, 30), (10, 50)]:
        name = f'Mark2_Trend_{fast}_{slow}'
        core = template.replace('n>=31', f'n>={slow+1}')
        core = core.replace('Avg(r,n-1,10)', f'Avg(r,n-1,{fast})').replace('Avg(r,n,10)', f'Avg(r,n,{fast})')
        core = core.replace('Avg(r,n-1,30)', f'Avg(r,n-1,{slow})').replace('Avg(r,n,30)', f'Avg(r,n,{slow})')
        source = f'#define SCALP_MODE false\n#define DEFAULT_TAG "{name}"\n' + core
        (output / (name + '.mq5')).write_text(source)
        variants.append({'id': name, 'kind': 'GENERATED_FROM_EXISTING_TESTER_BASELINE',
                         'fast': fast, 'slow': slow, 'direction': 'LONG_ONLY',
                         'execution': 'STRATEGY_TESTER_ONLY', 'compile_status': 'NOT_COMPILED',
                         'performance': None, 'sha256': hashlib.sha256(source.encode()).hexdigest()})
    save(output / 'manifest.json', variants)
    return variants


def research_cycle():
    DATA.mkdir(exist_ok=True)
    errors, repositories = [], {}
    for index, query in enumerate(QUERIES):
        try:
            result = api('search/repositories?' + urllib.parse.urlencode({'q': query, 'sort': 'stars' if index == 0 else 'updated', 'per_page': 3}))
            for repo in result.get('items', []):
                repositories[repo['full_name']] = repo
        except Exception as error:
            errors.append({'stage': 'discovery', 'query': query, 'error': str(error)[:250]})
    reviewed = []
    for name, repo in sorted(repositories.items()):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
            continue
        entry = {'repository': name, 'url': repo.get('html_url'),
                 'updated_at': repo.get('pushed_at'), 'stars': repo.get('stargazers_count'),
                 'license': (repo.get('license') or {}).get('spdx_id'),
                 'performance': None, 'status': 'SOURCE_SCREEN_ONLY', 'files': []}
        try:
            branch = urllib.parse.quote(repo['default_branch'], safe='')
            commit = api(f'repos/{name}/commits/{branch}')['sha']
            entry['commit'] = commit
            tree = api(f'repos/{name}/git/trees/{commit}?recursive=1')
            entry['tree_truncated'] = bool(tree.get('truncated'))
            paths = [p for p in tree.get('tree', []) if p.get('type') == 'blob'
                     and p.get('path', '').lower().endswith('.mq5') and p.get('size', 0) <= 150_000
                     and not re.search(r'(^|/)(tests?|examples?)(/|$)', p.get('path', ''), re.I)]
            paths.sort(key=lambda p: ('expert' not in p['path'].lower(), p['path']))
            for item in paths[:2]:
                blob = api(f'repos/{name}/git/blobs/{item["sha"]}')
                if blob.get('encoding') != 'base64' or blob.get('size', 0) > 150_000:
                    continue
                text = base64.b64decode(blob['content'], validate=False).decode('utf-8', errors='replace')
                analysis = inspect_source(text)
                # Store inert JSON evidence, never run or compile external code.
                save(DATA / 'sources' / (analysis['sha256'] + '.json'),
                     {'repository': name, 'commit': commit, 'path': item['path'], 'text': text, 'analysis': analysis})
                entry['files'].append({'path': item['path'], **analysis})
        except Exception as error:
            entry['error'] = str(error)[:250]
        reviewed.append(entry)
    generated = build_candidates()
    status = {'agent': 'JARVIS MARK 2', 'role': 'EA RESEARCH AND DEVELOPMENT',
              'observed_unix': time.time(), 'status': 'RESEARCH_COMPLETE' if not errors else 'RESEARCH_PARTIAL',
              'runtime': 'GITHUB_ACTIONS' if os.environ.get('GITHUB_ACTIONS') == 'true' else ('LOCAL_MAC' if __import__('sys').platform == 'darwin' else 'INDEPENDENT_HOST'),
              'cloud_deployed': os.environ.get('GITHUB_ACTIONS') == 'true', 'broker_orders_sent': 0, 'paid_services': False,
              'repositories': reviewed, 'generated_candidates': generated, 'errors': errors,
              'best_ea': None, 'winner_status': 'NO_VERIFIED_WINNER',
              'next_tasks': ['Review source and license before reuse', 'Compile generated EA on isolated MT5 tester',
                             'Collect broker-cost-aware forward-demo evidence before ranking'],
              'limitations': ['Source heuristics do not establish profitability or safety',
                             'Generated variants reuse an unproven long-only baseline',
                             'No new backtest or broker trade is automatically started',
                             'No LLM connected; this is a deterministic autonomous research worker']}
    save(DATA / 'status.json', status)
    registry_path = DATA / 'registry.json'
    try:
        registry = json.loads(registry_path.read_text())
    except (OSError, ValueError):
        registry = {}
    for entry in reviewed:
        registry[entry['repository']] = {**entry, 'last_reviewed_unix': status['observed_unix']}
    save(registry_path, dict(sorted(registry.items(), key=lambda item: item[1]['last_reviewed_unix'], reverse=True)[:100]))
    with (DATA / 'journal.jsonl').open('a') as journal:
        journal.write(json.dumps({'ts': status['observed_unix'], 'status': status['status'],
                                 'repositories': len(reviewed), 'candidates': len(generated), 'errors': errors}) + '\n')
    return status


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8766', 'localhost:8766'):
            self.send_error(403); return
        paths = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                 '/status.json': ('data/status.json', 'application/json')}
        item = paths.get(self.path.split('?', 1)[0])
        if not item:
            self.send_error(404); return
        try:
            body = (ROOT / item[0]).read_bytes()
        except FileNotFoundError:
            self.send_error(503, 'Research starting'); return
        self.send_response(200)
        self.send_header('Content-Type', item[1] + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(body)


def loop():
    while True:
        try:
            research_cycle()
        except Exception as error:
            save(DATA / 'status.json', {'agent': 'JARVIS MARK 2', 'observed_unix': time.time(),
                 'status': 'FAILED', 'error': str(error)[:250], 'broker_orders_sent': 0})
        time.sleep(3600)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.once:
        result = research_cycle()
        print(json.dumps({'status': result['status'], 'repositories': len(result['repositories']),
                          'generated': len(result['generated_candidates']), 'errors': result['errors']}))
    else:
        threading.Thread(target=loop, daemon=True).start()
        ThreadingHTTPServer(('127.0.0.1', 8766), Handler).serve_forever()
