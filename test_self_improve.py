import hashlib,json,shutil,tempfile,unittest
from pathlib import Path
from self_improve import repair,probe,run_cycle
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent if HERE.name=='tests' else HERE
TEMPLATE=(ROOT/'templates/JarvisTesterCore.mqh' if (ROOT/'templates/JarvisTesterCore.mqh').exists() else ROOT/'JarvisTesterCore.mqh').read_text()
class ImprovementTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'),'Host C++ compiler unavailable')
    def test_risk_repair_rejects_bad_inputs_and_keeps_budget_properties(self):
        self.assertFalse(probe(TEMPLATE,'FINITE_RISK_INPUTS')['passed'])
        candidate=repair(TEMPLATE,'FINITE_RISK_INPUTS')
        self.assertTrue(probe(candidate,'FINITE_RISK_INPUTS')['passed'])
        self.assertIn('!MQLInfoInteger(MQL_TESTER)',candidate)
    def test_unapproved_recipe_and_non_tester_source_rejected(self):
        with self.assertRaises(ValueError):repair(TEMPLATE,'INCREASE_RISK')
        with self.assertRaises(ValueError):repair(TEMPLATE.replace('!MQLInfoInteger(MQL_TESTER)','false'),'FINITE_RISK_INPUTS')
    @unittest.skipUnless(shutil.which('c++'),'Host C++ compiler unavailable')
    def test_bound_and_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'generated').mkdir();(root/'generated/Mark2_Trend_5_20.mq5').write_text(TEMPLATE)
            status={'generated_candidates':[{'id':'Mark2_Trend_5_20','sha256':hashlib.sha256(TEMPLATE.encode()).hexdigest()}]}
            a=run_cycle(root,status);self.assertEqual(len(a['attempts']),1)
            b=run_cycle(root,status);self.assertEqual(len(b['attempts']),2)
            c=run_cycle(root,status);self.assertEqual(len(c['attempts']),2);self.assertEqual(c['status'],'WAITING_FOR_NEW_EVIDENCE')
            self.assertFalse(c['trading_deployed'])
            for item in c['attempts']:self.assertEqual(item['native_compile'],'NOT_RUN')
    def test_hash_tamper_cannot_generate_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'generated').mkdir();(root/'generated/Mark2_Trend_5_20.mq5').write_text(TEMPLATE)
            self.assertEqual(run_cycle(root,{'generated_candidates':[{'id':'Mark2_Trend_5_20','sha256':'bad'}]})['attempts'],[])
if __name__=='__main__':unittest.main()
