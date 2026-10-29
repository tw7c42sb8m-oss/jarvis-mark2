import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import agent
import reuse

class ResearchTests(unittest.TestCase):
    def test_reused_signal_adapter_has_no_executor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('upstream.json','Geraked-3MACD.mq5','Geraked-MIT-LICENSE.txt'):
                (root/name).write_bytes((agent.ROOT/name).read_bytes())
            result=reuse.build(root,lambda route:self.fail('Pinned source should not need network'))
            source=(root/'generated/Mark2_Geraked_3MACD_SignalOnly.mq5').read_text()
            self.assertNotIn('OrderSend',source)
            self.assertNotIn('ea.',source)
            self.assertIn('ReverseSignals=true',source)
            self.assertIn('CopyBuffer(handles[0],0,0,BuffSize,M1)!=BuffSize',source)
            self.assertEqual(result['execution'],'STRATEGY_TESTER_SIGNAL_LOG_ONLY')

    def test_unexpected_signal_side_effect_is_rejected(self):
        with self.assertRaises(ValueError):
            reuse.function('bool BuySignal() { OrderSend(x);\n    double in = Ask(); return true; }','BuySignal')

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
        with tempfile.TemporaryDirectory() as folder, patch.object(agent,'DATA',Path(folder)), patch.object(agent,'api',side_effect=OSError('offline')), patch.object(agent,'build_candidates',return_value=[]), patch.object(agent,'reuse_candidate',side_effect=OSError('offline')), patch.object(agent,'cloud_cycle',return_value={'fleet_status':'COMPLETED','counts':{'workers':0}}), patch.object(agent,'bounded_crawl',return_value={'state':{'status':'WATCHING_FOR_SOURCE_UPDATES'},'source_snapshot':{'repositories':[]}}):
            status=agent.research_cycle()
            self.assertEqual(status['status'],'RESEARCH_PARTIAL')
            self.assertIsNone(status['best_ea'])
            self.assertEqual(len(status['errors']),6)
            self.assertEqual(status['broker_orders_sent'],0)

if __name__=='__main__':unittest.main()
