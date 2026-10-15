"""Explicit runtime references and test-network guards, without provisioning.

References identify existing host-owned integrations. Presence is never READY,
deployment, provider execution or financial authorization. No secret is loaded.
"""
from dataclasses import dataclass
import hashlib
import json
import re

SEPOLIA_CHAIN_ID = 11155111
REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")

@dataclass(frozen=True)
class RuntimeReferences:
    chain_id: int
    test_token: str
    token_decimals: int
    wallet_ref: str
    journal_ref: str
    oracle_ref: str
    settlement_ref: str
    asset_control_ref: str

    @classmethod
    def from_mapping(cls, value):
        fields=set(cls.__dataclass_fields__)
        if not isinstance(value,dict) or set(value)!=fields:
            raise ValueError("exact non-secret runtime reference fields required")
        if type(value["chain_id"]) is not int or value["chain_id"]!=SEPOLIA_CHAIN_ID:
            raise ValueError("only the approved Sepolia chain is supported")
        token=value["test_token"]
        if not isinstance(token,str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}",token) or int(token,16)==0:
            raise ValueError("the previously approved Sepolia test token binding is required")
        if type(value["token_decimals"]) is not int or not 0<=value["token_decimals"]<=255:
            raise ValueError("explicit token unit precision required")
        for key in fields-{"chain_id","test_token","token_decimals"}:
            if not isinstance(value[key],str) or REFERENCE.fullmatch(value[key]) is None:
                raise ValueError("opaque existing reference required: "+key)
        return cls(**value)

    def guard_asset(self, chain_id, token):
        if type(chain_id) is not int or chain_id!=self.chain_id:
            raise ValueError("execution chain differs from configured Sepolia binding")
        if not isinstance(token,str) or token.lower()!=self.test_token.lower():
            raise ValueError("execution asset differs from the approved configured token")
        return {"chainId":self.chain_id,"token":self.test_token,
                "decimals":self.token_decimals,"meaning":"configuration match only, no execution permission"}

    def identity(self):
        # Hash the explicit non-secret descriptor, never environment/credentials.
        descriptor={k:getattr(self,k) for k in self.__dataclass_fields__}
        return {"digest":hashlib.sha256(json.dumps(descriptor,sort_keys=True,
                        separators=(",", ":")).encode()).hexdigest(),
                "configuration":"PRESENT_UNVERIFIED", "operationsREADY":"NOT_VERIFIED",
                "providerExecution":"NOT_RUN", "deployment":"NOT_RUN"}
