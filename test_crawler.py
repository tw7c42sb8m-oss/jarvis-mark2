import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from spider_crawler import Crawler, bounded_crawl
from spider_hub import SpiderHub

class CrawlerTests(unittest.TestCase):
    def test_cloud_cursor_advances_instead_of_refetching_first_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            key=['test/repo','a'*40,'Experts/Test.mq5']
            (root/'data/cloud-crawler.json').write_text(json.dumps({'seen_sources':[key]}))
            with patch.object(Crawler,'expand_frontier',return_value=None),patch('spider_crawler.urllib.request.urlopen',side_effect=AssertionError('Already visited pinned source must not be fetched again')):
                result=bounded_crawl(root,self.status(b'x'))
            self.assertEqual(result['state']['visited'],0)
            saved=json.loads((root/'data/cloud-crawler.json').read_text())
            self.assertIn(key,saved['seen_sources'])
    def status(self,text,sha=None,path='Experts/Test.mq5'):
        return {'repositories':[{'repository':'test/repo','commit':'a'*40,'license':'MIT','files':[{'path':path,'sha256':sha or hashlib.sha256(text).hexdigest()}]}]}

    def test_real_fetch_saves_only_inert_evidence_and_stops_at_bound(self):
        body=b'raise RuntimeError("External source must not execute")'
        with tempfile.TemporaryDirectory() as folder:
            hub=SpiderHub(folder)
            crawler=Crawler(folder,hub,lambda:self.status(body),lambda root,status:{'status':'DEFERRED_TO_CLOUD_SUPERVISOR','pid':None},max_requests=1,pause_seconds=0,stop_when_idle=True)
            with patch('spider_crawler.urllib.request.urlopen',return_value=io.BytesIO(body)):
                crawler.run()
            self.assertEqual(crawler.state['visited'],1)
            self.assertEqual(crawler.state['status'],'BOUNDED_CRAWL_COMPLETE')
            self.assertEqual(len(list((Path(folder)/'data/sources').glob('*.json'))),1)
            self.assertFalse(crawler.state['external_code_executed'])

    def test_checksum_mismatch_does_not_enter_source_store(self):
        with tempfile.TemporaryDirectory() as folder:
            crawler=Crawler(folder,SpiderHub(folder),lambda:self.status(b'x',sha='0'*64),lambda r,s:{'status':'DEFERRED','pid':None},max_requests=1,pause_seconds=0)
            with patch('spider_crawler.urllib.request.urlopen',return_value=io.BytesIO(b'x')):crawler.run()
            self.assertEqual(crawler.state['failed'],1)
            self.assertEqual(crawler.state['visited'],0)
            self.assertFalse((Path(folder)/'data/sources').exists())

    def test_parent_path_is_not_a_frontier_target(self):
        with tempfile.TemporaryDirectory() as folder:
            crawler=Crawler(folder,SpiderHub(folder),lambda:self.status(b'x',path='../secret.mq5'),lambda r,s:None)
            self.assertEqual(crawler.frontier(),[])

if __name__=='__main__':unittest.main()
