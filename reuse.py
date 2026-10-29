"""Reuse a pinned MIT EA's signal logic; never import its order executor."""
import base64
import hashlib
import json
import re

REPOSITORY = 'geraked/metatrader5'
COMMIT = 'd3eb29c382acf715727d5cd6a0414151e821fc2d'


def function(source, name):
    match = re.search(r'bool\s+' + re.escape(name) + r'\s*\(\)\s*\{', source)
    if not match:
        raise ValueError('Pinned signal function missing')
    start, depth = match.end(), 1
    for index in range(start, len(source)):
        if source[index] == '{': depth += 1
        if source[index] == '}': depth -= 1
        if depth == 0:
            body = source[start:index]
            # This exact pinned source places only execution after this marker.
            marker = '    double in = '
            if body.count(marker) != 1:
                raise ValueError('Unexpected upstream signal layout')
            logic = body.split(marker)[0]
            if re.search(r'OrderSend|ea\.|#import|#include|WebRequest', logic):
                raise ValueError('Execution dependency found in signal body')
            return 'bool ' + name + '() {\n' + logic + '\n    return true;\n}\n'
    raise ValueError('Unbalanced upstream signal function')


def build(root, api):
    def fetch(path):
        item = api(f'repos/{REPOSITORY}/contents/{path}?ref={COMMIT}')
        if item.get('encoding') != 'base64' or item.get('size', 0) > 150_000:
            raise ValueError('Source size or encoding invalid')
        return base64.b64decode(item['content']).decode('utf-8-sig')
    pinned=root/'upstream.json'
    if pinned.is_file():
        provenance=json.loads(pinned.read_text())
        source=(root/'Geraked-3MACD.mq5').read_text()
        license_text=(root/'Geraked-MIT-LICENSE.txt').read_text()
        if provenance.get('commit') != COMMIT or provenance.get('repository') != REPOSITORY:
            raise ValueError('Unexpected cached upstream identity')
        if hashlib.sha256(source.encode()).hexdigest() != provenance.get('sha256') or hashlib.sha256(license_text.encode()).hexdigest() != provenance.get('license_sha256'):
            raise ValueError('Pinned upstream checksum mismatch')
    else:
        source = fetch('Experts/3MACD.mq5')
        license_text = fetch('LICENSE')
    if 'MIT License' not in license_text or 'Geraked' not in license_text:
        raise ValueError('Expected MIT license unavailable')
    buy, sell = function(source, 'BuySignal'), function(source, 'SellSignal')
    # No EAUtils, grid, position management, DLLs or broker execution are copied.
    header = '// Derived signal logic: Copyright 2023, Geraked. MIT license; see Geraked-MIT-LICENSE.txt.\n'
    header += f'// Source: https://github.com/{REPOSITORY}/blob/{COMMIT}/Experts/3MACD.mq5\n'
    adapter = header + '''#property strict
#property version "1.00"
input bool ReverseSignals=true; // Retain upstream 3MACD reverse convention.
const int BuffSize=32;
int handles[3];
double M1[],M2[],M3[];
datetime lastBar=0;
int OnInit() {
    if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
    for(int i=0;i<3;i++) handles[i]=INVALID_HANDLE;
    handles[0]=iMACD(_Symbol,_Period,5,8,1,PRICE_CLOSE);
    handles[1]=iMACD(_Symbol,_Period,13,21,1,PRICE_CLOSE);
    handles[2]=iMACD(_Symbol,_Period,34,144,1,PRICE_CLOSE);
    for(int i=0;i<3;i++) if(handles[i]==INVALID_HANDLE) return INIT_FAILED;
    return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) {
    for(int i=0;i<3;i++) if(handles[i]!=INVALID_HANDLE) IndicatorRelease(handles[i]);
}
''' + buy + sell + '''
void OnTick() {
    if(!MQLInfoInteger(MQL_TESTER)) return;
    datetime bar=iTime(_Symbol,_Period,1);
    if(bar==0 || bar==lastBar) return;
    for(int i=0;i<3;i++) if(BarsCalculated(handles[i])<144+BuffSize) return;
    if(CopyBuffer(handles[0],0,0,BuffSize,M1)!=BuffSize) return;
    if(CopyBuffer(handles[1],0,0,BuffSize,M2)!=BuffSize) return;
    if(CopyBuffer(handles[2],0,0,BuffSize,M3)!=BuffSize) return;
    ArraySetAsSeries(M1,true); ArraySetAsSeries(M2,true); ArraySetAsSeries(M3,true);
    lastBar=bar;
    int side=BuySignal()?1:(SellSignal()?-1:0);
    if(ReverseSignals) side=-side;
    if(side!=0) PrintFormat("MARK2_SIGNAL_ONLY %s %s %s %d",_Symbol,EnumToString(_Period),TimeToString(bar),side);
}
'''
    if any(word in adapter for word in ('OrderSend', 'CTrade', 'ea.', '#include', '#import', 'WebRequest')):
        raise ValueError('Unexpected execution surface in generated signal adapter')
    output=root/'generated'; output.mkdir(exist_ok=True)
    (output/'Mark2_Geraked_3MACD_SignalOnly.mq5').write_text(adapter)
    (output/'Geraked-MIT-LICENSE.txt').write_text(license_text)
    manifest={'id':'Mark2_Geraked_3MACD_SignalOnly', 'upstream':REPOSITORY, 'commit':COMMIT,
              'license':'MIT', 'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
              'sha256':hashlib.sha256(adapter.encode()).hexdigest(), 'kind':'REUSED_UPSTREAM_SIGNAL_LOGIC',
              'execution':'STRATEGY_TESTER_SIGNAL_LOG_ONLY', 'compile_status':'NOT_COMPILED',
              'performance':None, 'direction':'BUY_AND_SELL_SIGNALS',
              'excluded':['EAUtils executor','grid','martingale','upstream default IgnoreSL/IgnoreTP'],
              'limitations':['Not compiled on MT5', 'No performance test or trades',
                             'Signal equivalence with upstream not yet replay-verified']}
    (output/'reuse-manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest
