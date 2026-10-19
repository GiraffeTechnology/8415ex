"""Explicit observation configuration, never execution authority or a scheduler.

The host supplies its previously selected test settings. This module neither
chooses production policy nor reads credentials, environment, files or RPCs.
"""
from dataclasses import dataclass
import hashlib
import json

from .runtime_references import RuntimeReferences
from .workbench import RuntimeBinding


@dataclass(frozen=True)
class ObservationPolicy:
    confirmation_depth: int
    reorg_window_blocks: int
    rpc_timeout_ms: int
    registration_timeout_ms: int
    unknown_enquiry_interval_ms: int
    queue_retry_interval_ms: int
    max_pending_operations: int

    @classmethod
    def from_mapping(cls, value):
        fields = set(cls.__dataclass_fields__)
        if type(value) is not dict or set(value) != fields:
            raise ValueError('exact explicit observation policy fields required')
        for key in fields:
            if type(value[key]) is not int or not 1 <= value[key] <= 2147483647:
                raise ValueError('positive bounded integer required: ' + key)
        return cls(**value)

    def descriptor(self):
        value = {key: getattr(self, key) for key in self.__dataclass_fields__}
        # Revalidate direct dataclass construction too. No default or inferred
        # relation between confirmation depth and observation window is imposed.
        self.from_mapping(value)
        return value


def configuration_snapshot(references, policy):
    if type(references) is not RuntimeReferences or type(policy) is not ObservationPolicy:
        raise ValueError('existing runtime references and explicit observation policy required')
    descriptor = {key: getattr(references, key) for key in references.__dataclass_fields__}
    RuntimeReferences.from_mapping(descriptor)
    descriptor = {'schema': '8415ex-observation-configuration/1',
                  'references': descriptor, 'observationPolicy': policy.descriptor()}
    encoded = json.dumps(descriptor, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True).encode('utf-8')
    return {'descriptor': descriptor, 'sha256': hashlib.sha256(encoded).hexdigest(),
            'configuration': 'PRESENT_UNVERIFIED', 'authority': 'NOT_GRANTED',
            'operationsREADY': 'NOT_VERIFIED', 'providerExecution': 'NOT_RUN',
            'meaning': 'configuration identity only; no polling, retry, confirmation or acceptance performed'}


class PolicyRuntimeBinding(RuntimeBinding):
    """Expose a configuration snapshot beside the original domain observation.

    The original checked gateway still owns authorization, atomic state checks,
    confirmation and unknown-result handling. These parameters do not silently
    replace its settings and do not launch a second runtime or retry loop.
    """
    def __init__(self, *args, references, observation_policy, **kwargs):
        super().__init__(*args, **kwargs)
        self._configuration = configuration_snapshot(references, observation_policy)

    def snapshot(self):
        value = super().snapshot()
        # A fresh nested value protects the frozen configuration from a caller's
        # mutation. Configuration observation does not change business revision.
        value['configuration'] = json.loads(json.dumps(self._configuration))
        return value
