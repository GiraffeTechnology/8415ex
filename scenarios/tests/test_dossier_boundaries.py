"""Materials must be observed, not inferred from labels or empty containers."""
import unittest
from pathlib import Path
from unittest.mock import patch
from scenarios import dossier, stages, matrix

ROOT = str(Path(__file__).resolve().parents[2])
def scenario():
    return {'scenarioId':'DEMO-01','title':'fixture','mainPath':'fixture','setup':{},'steps':[], 'expectations':[]}
def item(s, name):
    return next(x for x in dossier.for_scenario(s)['items'] if x['item']==name)

class MaterialBoundaries(unittest.TestCase):
    def test_case_label_cannot_replace_escrow_facts(self):
        s=scenario();s['expectations']=[{'cases':['T-11']}]
        self.assertEqual(item(s,'per-segment escrow result')['status'],'gap')
    def test_empty_setup_values_are_gaps(self):
        s=scenario();s['setup']={'receipt':{},'accounts':None,'prices':{},'gasConditions':[]}
        self.assertEqual(item(s,'preset receipt and accounts')['status'],'gap')
        self.assertEqual(item(s,'test prices and gas conditions')['status'],'gap')
    def test_empty_facts_are_not_results(self):
        s=scenario();s['steps']=[{'facts':{'segmentFunds':{}}}]
        self.assertEqual(item(s,'per-segment escrow result')['status'],'gap')
    def test_empty_step_and_expectation_are_not_records(self):
        s=scenario();s['steps']=[{}];s['expectations']=[{}]
        self.assertEqual(item(s,'execution steps')['status'],'gap')
        self.assertEqual(item(s,'actual result and failure detail')['status'],'gap')
    def test_event_module_reference_is_not_recorded_events(self):
        self.assertEqual(item(scenario(),'recorded events')['status'],'gap')
    def test_positions_require_one_nonempty_snapshot(self):
        s=scenario();s['steps']=[{'facts':{'owner':'a','holder':'a'}},{'facts':{'ownerPosition':0,'holderPosition':0,'registeredPrefixLegs':0}}]
        self.assertEqual(item(s,'owner, holder and the registered prefix reached')['status'],'gap')
    def test_unknown_stage_is_not_agreement(self):
        with patch.dict(matrix.CASE_STAGE,{'T-01':99}):
            self.assertFalse(stages.build(ROOT)['agreesWithMatrix'])
    def test_existing_path_is_explicitly_not_execution_evidence(self):
        row=stages.build(ROOT)['stages'][0]['developedHere'][0]
        self.assertEqual(row.get('verificationScope'),'path-existence-only')
        self.assertFalse(row.get('implementationVerified',True))

class ScenarioBindingBoundaries(unittest.TestCase):
    def test_another_demo_timeline_cannot_replace_this_demo_evidence(self):
        import copy
        from scenarios.demos import DEMOS
        from scenarios.harness import run_all
        report=run_all(list(DEMOS))
        first=copy.deepcopy(report['scenarios'][0])
        other=report['scenarios'][1]
        replacement=next(s['facts']['auditTimeline'] for s in other['steps'] if 'auditTimeline' in s['facts'])
        target=next(s['facts'] for s in first['steps'] if 'auditTimeline' in s['facts'])
        target['auditTimeline']=replacement
        self.assertEqual(item(first,'recorded events')['status'],'gap')

    def test_null_expected_and_observed_do_not_establish_a_result(self):
        s=scenario();s['expectations']=[{'name':'empty placeholder','expected':None,'observed':None,'outcome':'passed','detail':None}]
        self.assertEqual(item(s,'actual result and failure detail')['status'],'gap')

    def test_empty_collection_can_be_an_observed_empty_result(self):
        s=scenario();s['expectations']=[{'name':'no outstanding refunds','expected':[],'observed':[],'outcome':'passed','detail':'all pending refunds were settled'}]
        self.assertEqual(item(s,'actual result and failure detail')['status'],'recorded')

    def test_timeline_and_view_from_other_demo_cannot_replace_the_pair(self):
        import copy
        from scenarios.demos import DEMOS
        from scenarios.harness import run_all
        report=run_all(list(DEMOS))
        first=copy.deepcopy(report['scenarios'][0])
        other=next(s['facts'] for s in report['scenarios'][1]['steps'] if 'auditTimeline' in s['facts'])
        target=next(s['facts'] for s in first['steps'] if 'auditTimeline' in s['facts'])
        target.update(auditTimeline=other['auditTimeline'],auditBusinessView=other['auditBusinessView'])
        self.assertEqual(item(first,'recorded events')['status'],'gap')

    def test_duplicate_demo_does_not_count_as_complete_coverage(self):
        from scenarios.demos import DEMOS
        from scenarios.harness import run_all
        report=run_all(list(DEMOS))
        report['scenarios'].append(report['scenarios'][0])
        self.assertFalse(dossier.build(report)['allItemsCarried'])

    def test_undeclared_demo_does_not_count_as_complete_coverage(self):
        from scenarios.demos import DEMOS
        from scenarios.harness import run_all
        report=run_all(list(DEMOS))
        report['scenarios'].append(dict(report['scenarios'][0],scenarioId='DEMO-unknown'))
        self.assertFalse(dossier.build(report)['allItemsCarried'])
