import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import agent

class ResearchTests(unittest.TestCase):
    def test_source_is_data_and_flags_are_not_profit(self):
        result=agent.inspect_source('#import "evil.dll"\nWebRequest(); // martingale SL TP\nOrderSend(x);')
        self.assertTrue(result['checks']['uses_dll_import'])
        self.assertTrue(result['checks']['mentions_martingale_or_grid'])
        self.assertEqual(result['profitability'],'UNPROVEN')

    def test_generated_variants_are_tester_only_and_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'templates').mkdir()
            template=agent.ROOT/'templates/JarvisTesterCore.mqh'
            if not template.is_file():template=agent.ROOT/'JarvisTesterCore.mqh'
            (root/'templates/JarvisTesterCore.mqh').write_text(template.read_text())
            with patch.object(agent,'ROOT',root):
                variants=agent.build_candidates()
            self.assertEqual(len({c['sha256'] for c in variants}),3)
            for candidate in variants:
                source=(root/'generated'/(candidate['id']+'.mq5')).read_text()
                self.assertIn('if(!MQLInfoInteger(MQL_TESTER)',source)
                self.assertIn('TargetEquity>0',source)
                self.assertIsNone(candidate['performance'])
                self.assertIn('Avg(r,n,'+str(candidate['slow'])+')',source)

    def test_network_failure_is_explicit_not_success_or_winner(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(agent,'DATA',Path(folder)), patch.object(agent,'api',side_effect=OSError('offline')), patch.object(agent,'build_candidates',return_value=[]):
            status=agent.research_cycle()
            self.assertEqual(status['status'],'RESEARCH_PARTIAL')
            self.assertIsNone(status['best_ea'])
            self.assertEqual(len(status['errors']),2)
            self.assertEqual(status['broker_orders_sent'],0)

if __name__=='__main__':unittest.main()
