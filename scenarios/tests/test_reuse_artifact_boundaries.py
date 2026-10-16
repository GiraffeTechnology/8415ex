"""Regression boundaries for the reuse and declared-artifact development batch."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scenarios import cli, reuse, evidence_index

ROOT = str(Path(__file__).resolve().parents[2])

class ReuseArtifactBoundaries(unittest.TestCase):
    def test_bare_undeclared_import_is_not_dropped(self):
        self.assertEqual(reuse._attribute({'exchange.new_dependency': []}, set()),
                         {'exchange.new_dependency': []})

    def test_import_parser_handles_python_syntax_not_string_lookalikes(self):
        with tempfile.TemporaryDirectory() as tmp:
            package=Path(tmp)/'scenarios';package.mkdir()
            (package/'fixture.py').write_text('"""\nfrom exchange.fake import ghost\n"""\nfrom exchange.model import (\n Asset as Item,\n REGISTRATION_PATHS,\n)\nimport exchange.ids as ids, exchange.other\n')
            found=reuse.source_imports(tmp)['modules']
        self.assertNotIn('exchange.fake', found)
        self.assertEqual(found['exchange.model'], ['Asset','REGISTRATION_PATHS'])
        self.assertIn('exchange.ids', found)
        self.assertIn('exchange.other', found)

    def test_runtime_unresolved_name_makes_reuse_incomplete(self):
        with patch.object(reuse, 'observed_domain_modules', return_value=[{'error':None,'unresolvedNames':['missing']}]), \
             patch.object(reuse, 'declared_coverage', return_value={'complete': True}):
            self.assertFalse(reuse.build()['complete'])

    def test_artifact_format_is_output_role_not_extension(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            json_path=str(Path(tmp)/'record.bin');text_path=str(Path(tmp)/'summary.json')
            cli.main(['run-all','--root',ROOT,'--json-out',json_path,'--text-out',text_path])
            document=json.loads(Path(json_path).read_text())
            slots=document['evidenceIndex']['artifacts']
            refs=document['evidenceIndex']['rows'][0]['artifactReferences']
            self.assertEqual([x['format'] for x in slots], ['json','text'])
            self.assertIsNotNone(refs[0]['pointerInArtifact'])
            self.assertIsNone(refs[1]['pointerInArtifact'])
            self.assertNotIn('index included', slots[1]['carries'])
            self.assertEqual(document['outputDeliveryPlan'],[json_path,text_path])

    def test_reuse_cli_refuses_unresolved_runtime_map(self):
        with patch.object(reuse,'build',return_value={'complete':False,'declaredCoverage':{'complete':True}}), \
             patch.object(cli,'run_all',return_value={}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['reuse']),1)

    def test_delivery_reference_does_not_claim_saved_file_contains_final_status(self):
        slot=evidence_index._artifact_slots([{'path':'x','format':'json'}])[0]
        self.assertIn('externally captured final stdout JSON',slot['deliveryReportedBy'])
        self.assertNotIn('#/outputDelivery in the delivered record',slot['deliveryReportedBy'])
        ref=evidence_index._artifact_references(0,[])[0]
        self.assertIn('default text summary',ref['note'])

    def test_reuse_rejects_unsupported_output_flags(self):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(reuse,'build') as build:
            with self.assertRaises(SystemExit) as raised: cli.main(['reuse','--text-out','ignored'])
            self.assertEqual(raised.exception.code,2)
            build.assert_not_called()

    def test_new_imported_attribute_must_be_declared(self):
        imports={'modules':{'exchange.model':['Asset','new_name']},'tests':{}}
        with patch.object(reuse,'source_imports',return_value=imports):
            r=reuse.declared_coverage(ROOT)
        self.assertEqual(r['undeclaredNames']['exchange.model'],['new_name'])
        self.assertFalse(r['complete'])
