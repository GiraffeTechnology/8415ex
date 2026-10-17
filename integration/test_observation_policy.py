"""Authored configuration contracts; no live provider or production policy."""
import hashlib
import json
import unittest
from unittest.mock import patch

from exchange.observation_policy import ObservationPolicy, PolicyRuntimeBinding, configuration_snapshot
from exchange.runtime_references import RuntimeReferences
from exchange.workbench import RuntimeBinding


def settings():
    # Synthetic test inputs, not deployment defaults or an approved fee policy.
    return dict(confirmation_depth=2, reorg_window_blocks=8, rpc_timeout_ms=1000,
                registration_timeout_ms=5000, unknown_enquiry_interval_ms=2000,
                queue_retry_interval_ms=3000, max_pending_operations=16)


def refs():
    return RuntimeReferences.from_mapping(dict(chain_id=11155111,
        test_token='0x' + '1' * 40, token_decimals=6, wallet_ref='fixture-wallet',
        journal_ref='fixture-journal', oracle_ref='fixture-oracle',
        settlement_ref='fixture-settlement', asset_control_ref='fixture-control'))


class ObservationPolicyContracts(unittest.TestCase):
    def test_every_field_is_explicit_and_strict_integer(self):
        for field in settings():
            for bad in (True, False, 0, -1, 1.0, '1', None, 2147483648):
                with self.subTest(field=field, bad=bad):
                    value = settings(); value[field] = bad
                    with self.assertRaises(ValueError):
                        ObservationPolicy.from_mapping(value)
            value = settings(); del value[field]
            with self.assertRaises(ValueError):
                ObservationPolicy.from_mapping(value)
        value = settings(); value['credential'] = 'not-allowed'
        with self.assertRaises(ValueError):
            ObservationPolicy.from_mapping(value)

    def test_canonical_digest_and_no_ready_promotion(self):
        original = settings()
        policy = ObservationPolicy.from_mapping(original)
        left = configuration_snapshot(refs(), policy)
        right = configuration_snapshot(refs(), ObservationPolicy.from_mapping(dict(reversed(list(original.items())))))
        self.assertEqual(left, right)
        raw = json.dumps(left['descriptor'], sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        self.assertEqual(left['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(left['operationsREADY'], 'NOT_VERIFIED')
        self.assertEqual(left['authority'], 'NOT_GRANTED')
        self.assertEqual(left['providerExecution'], 'NOT_RUN')
        original['rpc_timeout_ms'] = 7
        self.assertEqual(policy.rpc_timeout_ms, 1000)

    def test_each_setting_changes_identity(self):
        baseline = configuration_snapshot(refs(), ObservationPolicy.from_mapping(settings()))['sha256']
        for field in settings():
            value = settings(); value[field] += 1
            with self.subTest(field=field):
                self.assertNotEqual(baseline, configuration_snapshot(refs(), ObservationPolicy.from_mapping(value))['sha256'])

    def test_direct_construction_cannot_skip_validation(self):
        value = settings(); value['rpc_timeout_ms'] = False
        with self.assertRaises(ValueError):
            configuration_snapshot(refs(), ObservationPolicy(**value))
        value = dict(vars(refs())); value['chain_id'] = 560048
        with self.assertRaises(ValueError):
            configuration_snapshot(RuntimeReferences(**value), ObservationPolicy.from_mapping(settings()))

    def test_original_snapshot_and_business_revision_preserved(self):
        gateway = object(); domain = object()
        binding = PolicyRuntimeBinding(domain, 'fixture-receipt', gateway=gateway,
            references=refs(), observation_policy=ObservationPolicy.from_mapping(settings()))
        with patch.object(RuntimeBinding, 'snapshot', return_value={'revision': 'original', 'state': {'pending': True}}) as original:
            first = binding.snapshot()
            first['configuration']['descriptor']['observationPolicy']['rpc_timeout_ms'] = 1
            second = binding.snapshot()
        self.assertEqual(original.call_count, 2)
        self.assertEqual(second['revision'], 'original')
        self.assertEqual(second['state'], {'pending': True})
        self.assertEqual(second['configuration']['descriptor']['observationPolicy']['rpc_timeout_ms'], 1000)
        self.assertIs(binding.exchange, domain)
        self.assertIs(binding.gateway, gateway)


if __name__ == '__main__':
    unittest.main()
