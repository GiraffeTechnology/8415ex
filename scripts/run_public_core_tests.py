"""Run exact source tests; explicitly inventory the separately verified private layer."""
import json
import sys
import unittest
from pathlib import Path

EXTERNAL = {
    'integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_cancel_unattempted_after_revoke_and_duplicate_refused',
    'integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_revoke_cas_replay_and_execution_after_revoke',
    'integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_route_fields_session_chain_and_foreign_task',
}

def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test

sys.path.insert(0, str(Path.cwd()))
name, directory = sys.argv[1:3]
loader = unittest.TestLoader()
suite = loader.discover(directory, top_level_dir='.' if name != 'ci' else None)
tests = list(flatten(suite))
ids = [test.id() for test in tests]
assert len(ids) == len(set(ids)), 'duplicate test IDs'
assert len(ids) == {'ci': 29, 'domain': 739, 'integration': 1525, 'scenarios': 628}[name], 'full inventory count mismatch'
external = set(ids) & EXTERNAL
assert external == (EXTERNAL if name == 'integration' else set()), 'private layer inventory mismatch'
core = [test for test in tests if test.id() not in EXTERNAL]
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(core))
record = {'suite': name, 'discoveredTests': len(tests), 'publicCoreRun': result.testsRun,
          'publicCoreSkipped': [test.id() for test, _ in result.skipped],
          'externalPrivateLayer': {'status': 'NOT_EXECUTED_HERE', 'testIds': sorted(external)},
          'failures': len(result.failures), 'errors': len(result.errors),
          'unexpectedSuccesses': len(result.unexpectedSuccesses),
          'expectedFailures': len(result.expectedFailures)}
ok = (not loader.errors and result.wasSuccessful() and not result.skipped and
      not result.expectedFailures and result.testsRun == len(core))
record['status'] = 'PASS_PUBLIC_CORE' if ok else 'FAIL_PUBLIC_CORE'
Path('/evidence', name + '-inventory.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
sys.exit(0 if ok else 1)
