import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mission_agents import evaluate, run_once, kickoff, _request

CODE='''#property strict
int OnInit(){if(!MQLInfoInteger(MQL_TESTER))return INIT_FAILED;return INIT_SUCCEEDED;}
double RiskLots(){return 0;} void X(){request.sl=1;request.tp=2;OrderCheck(x,y);long x=POSITION_MAGIC;}
'''
class MissionAgentsTests(unittest.TestCase):
    def fixture(self,root,**updates):
        (root/'generated').mkdir(exist_ok=True)
        (root/'generated/Example.mq5').write_text(CODE)
        candidate={'id':'Example','kind':'GENERATED_FROM_EXISTING_TESTER_BASELINE','sha256':hashlib.sha256(CODE.encode()).hexdigest(),'compile_status':'NOT_COMPILED','performance':None}
        candidate.update(updates)
        return {'repositories':[],'generated_candidates':[candidate]}, {'status':'COMPLETED','counts':{'workers':24,'completed':24}}
    def test_actual_processes_no_false_winner_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);status,fleet=self.fixture(root)
            result=run_once(root,status,fleet)
            self.assertEqual(result['status'],'COMPLETED')
            self.assertEqual(len({n['pid'] for n in result['nodes']}),4)
            self.assertTrue(all(n['started_unix']<=n['completed_unix'] for n in result['nodes']))
            self.assertIsNone(result['verified_winner']);self.assertEqual(result['objective_status'],'NOT_ACHIEVED')
            self.assertTrue(result['next_tasks']);self.assertFalse(result['results']['VALIDATION_REVIEW']['candidates'][0]['trading_enabled'])
            self.assertEqual(run_once(root,status,fleet)['run_id'],result['run_id']);self.assertEqual(kickoff(root,status,fleet)['status'],'UP_TO_DATE')
            self.assertTrue((root/'generated/mission-review.md').is_file())
            self.assertEqual(json.loads((root/'generated/mission-progress.json').read_text())['run_id'],result['run_id'])
    def test_hash_tamper_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);status,fleet=self.fixture(root,sha256='0'*64)
            result=evaluate('EVIDENCE_TRIAGE',_request(root,status,fleet))['candidates'][0]
            self.assertFalse(result['hash_verified']);self.assertIn('SOURCE_HASH_OR_FILE_INVALID',result['blockers'])
    def test_unknown_license_and_unpinned_source_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);status,fleet=self.fixture(root,kind='REUSED_UPSTREAM_SIGNAL_LOGIC',license=None,commit=None)
            result=evaluate('EVIDENCE_TRIAGE',_request(root,status,fleet))['candidates'][0]
            self.assertIn('LICENSE_PROVENANCE_UNCONFIRMED',result['blockers']);self.assertIn('UPSTREAM_COMMIT_NOT_PINNED',result['blockers'])
    def test_comment_guard_is_not_a_tester_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);status,fleet=self.fixture(root)
            text='// if(!MQLInfoInteger(MQL_TESTER))return INIT_FAILED;\nvoid X(){}'
            (root/'generated/Example.mq5').write_text(text);status['generated_candidates'][0]['sha256']=hashlib.sha256(text.encode()).hexdigest()
            request=_request(root,status,fleet);request['stage_results']={'EVIDENCE_TRIAGE':evaluate('EVIDENCE_TRIAGE',request)}
            row=evaluate('EA_ENGINEERING',request)['candidates'][0]
            self.assertFalse(row['static_hints']['tester_guard']);self.assertIn('STATIC_HINT_MISSING_TESTER_GUARD',row['blockers'])
    def test_untrusted_profit_claim_cannot_promote_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);status,fleet=self.fixture(root,compile_status='COMPILED',performance={'profit':1000000,'verified':True})
            result=run_once(root,status,fleet);decision=result['results']['MISSION_PLANNER']
            self.assertIsNone(decision['verified_winner']);self.assertEqual(decision['objective_status'],'NOT_ACHIEVED');self.assertFalse(decision['automatic_promotion'])
            self.assertIn('NATIVE_MT5_COMPILE_NOT_VERIFIED',result['results']['VALIDATION_REVIEW']['candidates'][0]['blockers'])
if __name__=='__main__':unittest.main()
