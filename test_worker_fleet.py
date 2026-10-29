import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import worker_fleet as fleet

class FleetTests(unittest.TestCase):
    def repo(self,text='// SL TP\nvoid OnTick(){}',license_id='MIT'):
        return {'repository':'example/research','license':license_id,'commit':'abc123','files':[{'path':'Experts/Research.mq5','sha256':hashlib.sha256(text.encode()).hexdigest()}]},text

    def source(self,root,repo,text):
        folder=Path(root)/'data/sources';folder.mkdir(parents=True)
        (folder/'fixture.json').write_text(json.dumps({'repository':repo['repository'],'commit':repo['commit'],'path':'Experts/Research.mq5','text':text}))

    def test_real_children_have_pids_and_results_without_executing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);sentinel=root/'MUST_NOT_EXIST'
            repo,text=self.repo("__import__('pathlib').Path("+repr(str(sentinel))+").write_text('EXECUTED')\n// SL TP Grid OrderSend")
            self.source(root,repo,text)
            result=fleet.run_once(root,{'observed_unix':123,'repositories':[repo]})
            self.assertEqual(result['status'],'COMPLETED')
            workers=[n for n in result['nodes'] if n['kind']=='DETERMINISTIC_TOOL_WORKER']
            self.assertEqual(len(workers),3)
            self.assertEqual(len({n['pid'] for n in workers}),3)
            self.assertTrue(all(n['pid']!=__import__('os').getpid() for n in workers))
            self.assertTrue(all(n['status']=='COMPLETED' and n['started_unix']<=n['completed_unix'] for n in workers))
            self.assertTrue(all(n['result']['external_code_executed'] is False for n in workers))
            self.assertFalse(sentinel.exists())
            self.assertEqual(result['counts']['launched'],3)
            ready=next(n['result'] for n in workers if n['task']=='CANDIDATE_READINESS')
            self.assertEqual(ready['decision'],'NOT_READY_FOR_TRADING')
            self.assertEqual(fleet.read_status(root)['run_id'],result['run_id'])

    def test_two_process_concurrency_bound_is_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo,_=self.repo()
            other={**repo,'repository':'example/other'}
            result=fleet.run_once(directory,{'repositories':[repo,other]})
            workers=[n for n in result['nodes'] if n['kind']=='DETERMINISTIC_TOOL_WORKER']
            intervals=sorted([(n['started_unix'],1) for n in workers]+[(n['completed_unix'],-1) for n in workers])
            active=peak=0
            for _,delta in intervals:
                active+=delta;peak=max(peak,active)
            self.assertLessEqual(peak,2)
            self.assertEqual(len(workers),6)
            self.assertEqual(result['counts']['completed'],6)

    def test_dead_supervisor_is_not_reported_as_working(self):
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)/'data';data.mkdir()
            fleet.atomic_json(data/'worker-fleet.json',{'status':'RUNNING','nodes':[
                {'id':'parent','kind':'DETERMINISTIC_SUPERVISOR','status':'RUNNING','pid':999999999},
                {'id':'child','kind':'DETERMINISTIC_TOOL_WORKER','status':'RUNNING','pid':999999998},
                {'id':'queued','kind':'DETERMINISTIC_TOOL_WORKER','status':'QUEUED','pid':None}]})
            result=fleet.read_status(directory)
            self.assertEqual(result['status'],'INTERRUPTED')
            self.assertEqual(result['nodes'][1]['status'],'INTERRUPTED')
            self.assertEqual(result['nodes'][2]['status'],'NOT_STARTED')

    def test_unknown_license_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo,_=self.repo(license_id='NOASSERTION')
            result=fleet.evaluate(directory,'LICENSE_CHECK',repo)
            self.assertEqual(result['decision'],'HOLD_UNKNOWN_LICENSE')
            self.assertFalse(result['license_metadata_recognized'])
            ready=fleet.evaluate(directory,'CANDIDATE_READINESS',repo)
            self.assertIn('LICENSE_UNCONFIRMED',ready['blockers'])
            self.assertIn('SOURCE_EVIDENCE_INCOMPLETE',ready['blockers'])

    def test_source_hash_and_commit_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            repo,text=self.repo();self.source(directory,repo,text+'\n// tampered')
            result=fleet.evaluate(directory,'SOURCE_STATIC_REVIEW',repo)
            self.assertEqual(result['matched_source_files'],0)
            self.assertEqual(result['rejected_sources'][0]['reason'],'SHA256_MISMATCH')
            repo['commit']='other-commit'
            self.assertEqual(fleet.evaluate(directory,'SOURCE_STATIC_REVIEW',repo)['matched_source_files'],0)

    def test_malformed_request_rejected_in_actual_child(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,fleet.__file__,'--child','LICENSE_CHECK','--root',directory],input='{"repository":";execute code"}',text=True,capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(json.loads(result.stdout)['status'],'FAILED')
            self.assertEqual(fleet.kickoff(directory,{'repositories':'invalid'})['status'],'INVALID_INPUT')

    def test_kickoff_does_not_launch_when_supervisor_alive(self):
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)/'data';data.mkdir();(data/'worker-fleet-supervisor.pid').write_text(str(__import__('os').getpid()))
            with patch.object(fleet.subprocess,'Popen') as spawn:
                repo,_=self.repo();result=fleet.kickoff(directory,{'repositories':[repo]})
                self.assertEqual(result['status'],'ALREADY_RUNNING');spawn.assert_not_called()

if __name__=='__main__':unittest.main()
