"""New audit/material commands preserve stdout-only publication boundaries."""
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from scenarios import cli

class UnifiedCommands(unittest.TestCase):
    def test_new_commands_reject_ignored_output_paths(self):
        for command in ('events','stages','dossier'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)/'report.json'
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    cli.main([command,'--json-out',str(output)])
                self.assertEqual(caught.exception.code,2)
                self.assertFalse(output.exists())

    def test_events_cli_has_valid_live_business_projection(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): status=cli.main(['events'])
        self.assertEqual(status,0)
        record=json.loads(output.getvalue())
        self.assertTrue(record['validReplay'])

    def test_material_commands_report_the_actual_six_scenarios(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): status=cli.main(['dossier'])
        record=json.loads(output.getvalue())
        self.assertEqual(status,0)
        self.assertEqual(record['scenarioCount'],6)
        self.assertTrue(record['allItemsCarried'])

    def test_events_missing_local_capability_fails_cli(self):
        from scenarios import events
        original=events.conformance
        def missing(root):
            report=original(root); report['localContractComplete']=False
            return report
        with patch.object(events,'conformance',side_effect=missing), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['events']),1)

    def test_run_all_blocks_each_material_failure(self):
        from scenarios import events, stages, dossier
        for module,key,message in ((events,'localContractComplete','event vocabulary'),
                                   (stages,'agreesWithMatrix','stage map'),
                                   (dossier,'allItemsCarried','demonstration dossier')):
            name='conformance' if module is events else 'build'
            original=getattr(module,name)
            def failed(*args,_original=original,_key=key,**kwargs):
                result=_original(*args,**kwargs); result[_key]=False
                return result
            with self.subTest(module=module.__name__), patch.object(module,name,side_effect=failed):
                built=cli._bundle('.')
                self.assertTrue(any(message in reason for reason in built['blocking']))
                self.assertFalse(built['allLocalPassed'])
