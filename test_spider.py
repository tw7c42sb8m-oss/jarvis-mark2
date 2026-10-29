import tempfile
import unittest
from pathlib import Path
from spider_hub import SpiderHub
from review_learning import review

class SpiderTests(unittest.TestCase):
    def test_real_route_persists_and_deduplicates_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            hub=SpiderHub(folder)
            hub.route('CLAUDE','CONTEXT','ARCHIVED_REVIEW',{'direct_model_connection':False},'LOCAL_REVIEW_ARCHIVE')
            SpiderHub(folder).route('CLAUDE','CONTEXT','ARCHIVED_REVIEW',{'direct_model_connection':False},'LOCAL_REVIEW_ARCHIVE')
            status=hub.snapshot()
            self.assertEqual(status['retained_packets'],1)
            packet=status['packets'][0]
            self.assertEqual(packet['via'],'SPIDER')
            self.assertFalse(packet['payload']['direct_model_connection'])
            self.assertEqual(len(packet['fingerprint']),64)

    def test_lessons_are_not_counted_again_on_ui_poll_or_duplicate_worker_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            node={'kind':'DETERMINISTIC_TOOL_WORKER','repository':'test/repo','result':{'commit':'a','blockers':['LICENSE_UNCONFIRMED']}}
            fleet={'status':'COMPLETED','run_id':'one','nodes':[node,node]}
            one=review(folder,fleet);two=review(folder,fleet)
            self.assertEqual(len(two['findings']),1)
            self.assertEqual(next(iter(two['findings'].values()))['reviews_seen'],1)
            self.assertFalse(two['automatic_trading_promotion'])
            fleet['run_id']='two';three=review(folder,fleet)
            self.assertEqual(next(iter(three['findings'].values()))['reviews_seen'],2)

    def test_dispatch_records_actual_supervisor_response(self):
        with tempfile.TemporaryDirectory() as folder:
            hub=SpiderHub(folder)
            result=hub.launch_workers(lambda root,cloud:{'status':'STARTED','pid':123}, {'observed_unix':1})
            self.assertEqual(hub.snapshot()['packets'][0]['payload']['supervisor_pid'],result['pid'])

if __name__=='__main__':unittest.main()
