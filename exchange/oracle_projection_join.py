"""Read the existing Oracle application projection API; never write a holder.

No URL, credential, provider, signer or registry is constructed by this module.
"""
from copy import deepcopy
import re

from .errors import require, DomainError
from .ids import canonical_json, digest
from .principal_journal_contract import PrincipalBinding

CODE = "EX_ORACLE_JOIN_REFUSED"
PREFIX = "/v1/oracle/projection"
BYTES32 = re.compile(r"\A0x[0-9a-fA-F]{64}\Z")
ADDRESS = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")
DECIMAL = re.compile(r"\A(0|[1-9][0-9]*)\Z")


class OracleProjectionReadError(DomainError):
    """Sanitized application-read outcome, never a registrar's business refusal."""
    def __init__(self, status, error_code):
        super().__init__(CODE, "Oracle projection read unavailable")
        self.observation_status = status
        self.error_code = error_code


def _read_error(status, body):
    # Only codes from the original Oracle application contract are exposed.
    codes = {
        400: {"TOKEN_ID_INVALID", "VERSION_INVALID", "INSTANT_INVALID"},
        404: {"INSTANT_NOT_COVERED", "UNKNOWN_TOKEN", "UNKNOWN_VERSION", "EMPTY_PROJECTION"},
        502: {"PROJECTION_SOURCE_MALFORMED", "PROJECTION_SOURCE_REFUSED",
              "PROJECTION_SOURCE_IDENTITY_MISMATCH", "POSITION_SOURCE_MALFORMED"},
        503: {"PROJECTION_SOURCE_NOT_CONFIGURED", "PROJECTION_BINDING_INVALID",
              "PROJECTION_SOURCE_UNAVAILABLE", "POSITION_SOURCE_UNAVAILABLE"},
    }
    code = body.get("errorCode") if type(body) is dict else None
    if type(code) is not str or code not in codes.get(status, set()):
        return OracleProjectionReadError("UNAVAILABLE", "ORACLE_READ_UNAVAILABLE")
    state = ("UNBOUND" if code == "PROJECTION_SOURCE_NOT_CONFIGURED" else
             "NOT_OBSERVED" if status == 404 else
             "READ_REFUSED" if status in (400, 502) or code == "PROJECTION_BINDING_INVALID" else
             "UNAVAILABLE")
    return OracleProjectionReadError(state, code)


def _decimal(value, bits):
    require(type(value) is str and len(value) <= 78
            and DECIMAL.fullmatch(value) is not None and int(value) < 2 ** bits,
            CODE, "canonical unsigned decimal string required")
    return value


def _hash(value):
    require(type(value) is str and BYTES32.fullmatch(value) is not None,
            CODE, "bytes32 required")
    return value.lower()


def _address(value):
    require(type(value) is str and ADDRESS.fullmatch(value) is not None,
            CODE, "address required")
    return value.lower()


def _source(value):
    require(type(value) is dict and set(value) == {"chainId", "contract", "registerId"},
            CODE, "exact Oracle source identity required")
    chain = _decimal(value["chainId"], 256)
    require(chain == "11155111", CODE, "EX Sepolia source required")
    return {"chainId": chain, "contract": _address(value["contract"]),
            "registerId": _hash(value["registerId"])}


def _entry(value):
    fields = {"version", "holder", "effectiveAt", "supersededAt",
              "recordCommitment", "previousCommitment", "registryReference"}
    require(type(value) is dict and set(value) == fields, CODE, "exact projection entry required")
    result = {key: _decimal(value[key], 64)
              for key in ("version", "effectiveAt", "supersededAt")}
    require(result["version"] != "0" and
            (result["supersededAt"] == "0" or
             int(result["supersededAt"]) > int(result["effectiveAt"])),
            CODE, "invalid projection interval")
    result["holder"] = _address(value["holder"])
    for key in ("recordCommitment", "previousCommitment", "registryReference"):
        result[key] = _hash(value[key])
    return result


class OracleProjectionJoin:
    """Consume only existing GET routes through the installed Oracle transport.

    read(method, path) returns (status, body) after the installed original
    transport has enforced its authenticated origin, timeout, byte limit and
    source/artifact identity. This object adds a defensive decoded body limit.
    It never reaches Kit directly or uses a token ID as a global source ID.

    verify_mapping(binding, facts) must authenticate the actual original
    EX asset/global-leg/native-operation to Oracle register/version/commitment
    and canonical record mapping. A registryReference locator is not that
    record, and accepting public JSON is not an implementation of this port.
    """
    def __init__(self, source, read, verify_mapping):
        self._source = _source(deepcopy(source))
        require(callable(read) and callable(verify_mapping), CODE, "installed original ports required")
        self._read = read
        self._verify_mapping = verify_mapping

    def _get(self, token_id, tail, fields):
        path = PREFIX + "/" + token_id + ("/" + tail if tail else "")
        result = self._read("GET", path)
        require(type(result) is tuple and len(result) == 2, CODE, "Oracle response required")
        status, raw = result
        require(type(status) is int, CODE, "Oracle response status required")
        if status != 200:
            raise _read_error(status, raw)
        require(type(raw) is dict, CODE, "Oracle response body required")
        body = deepcopy(raw)
        require(len(canonical_json(body).encode("ascii")) <= 65536,
                CODE, "decoded Oracle body exceeds bound")
        require(set(body) == {"tokenId", "source"} | set(fields)
                and body["tokenId"] == token_id and _source(body["source"]) == self._source,
                CODE, "Oracle source or token identity differs")
        return body

    def _head(self, token_id):
        body = self._get(token_id, "", ("registerId", "entryCount"))
        require(_hash(body["registerId"]) == self._source["registerId"],
                CODE, "Oracle register identity differs")
        return _decimal(body["entryCount"], 64)

    def inspect(self, binding, version, record_commitment, as_of, cutoff):
        """Return detached joined read facts; never manufacture release authority."""
        return self._inspect(binding, version, record_commitment, as_of, cutoff)

    def inspect_as_of(self, binding, as_of, cutoff):
        """Select the original covering record without guessing its version.

        This still requires the original canonical mapping verifier. A public
        projection entry or registry locator alone is not release authority.
        """
        require(type(binding) is PrincipalBinding, CODE, "original EX segment binding required")
        require(str(binding.asset.chain_id) == self._source["chainId"],
                CODE, "asset/source chain mismatch")
        token_id = _decimal(str(binding.asset.token_id), 256)
        as_of, cutoff = _decimal(as_of, 64), _decimal(cutoff, 64)
        body = self._get(token_id, "entry/as-of/" + as_of, ("instant", "entry"))
        require(body["instant"] == as_of, CODE, "Oracle instant differs")
        entry = _entry(body["entry"])
        require(int(entry["effectiveAt"]) <= int(as_of)
                and (entry["supersededAt"] == "0" or int(as_of) < int(entry["supersededAt"])),
                CODE, "entry does not cover requested instant")
        return self._inspect(binding, entry["version"], entry["recordCommitment"],
                             as_of, cutoff, selected_entry=entry)

    def _inspect(self, binding, version, record_commitment, as_of, cutoff,
                 selected_entry=None):
        """Bounded original version/holder/finality read, with optional selection."""

        require(type(binding) is PrincipalBinding, CODE, "original EX segment binding required")
        require(str(binding.asset.chain_id) == self._source["chainId"],
                CODE, "asset/source chain mismatch")
        token_id = _decimal(str(binding.asset.token_id), 256)
        version = _decimal(version, 64)
        require(version != "0", CODE, "registered version required")
        commitment = _hash(record_commitment)
        as_of, cutoff = _decimal(as_of, 64), _decimal(cutoff, 64)
        for attempt in range(2):
            before = self._head(token_id)
            require(int(before) >= int(version), CODE, "required registration version absent")
            entry = _entry(self._get(token_id, "entry/version/" + version, ("entry",))["entry"])
            require(entry["version"] == version and entry["recordCommitment"] == commitment,
                    CODE, "registration version or commitment differs")
            require(selected_entry is None or entry == selected_entry,
                    CODE, "Oracle selected entry changed during joined reads")
            require(int(entry["effectiveAt"]) <= int(as_of)
                    and (entry["supersededAt"] == "0" or int(as_of) < int(entry["supersededAt"])),
                    CODE, "entry does not cover requested instant")
            holder_body = self._get(token_id, "holder/as-of/" + as_of, ("instant", "holder"))
            final_body = self._get(token_id, "finality/as-of/" + as_of, ("instant", "final"))
            require(holder_body["instant"] == as_of and final_body["instant"] == as_of,
                    CODE, "Oracle instant differs")
            holder = _address(holder_body["holder"])
            require(holder == entry["holder"] and type(final_body["final"]) is bool,
                    CODE, "holder projection inconsistent or finality malformed")
            after = self._head(token_id)
            if after != before:
                continue
            facts = {"source": deepcopy(self._source), "projectionTokenId": token_id,
                     "entryCount": after, "entry": entry, "asOf": as_of,
                     "holderAsOf": holder, "finalAsOf": final_body["final"], "cutoff": cutoff,
                     "bindingDigest": binding.binding_digest,
                     "nativeOperationId": binding.operation_id,
                     "journalReference": binding.journal_reference}
            require(self._verify_mapping(binding, deepcopy(facts)) is True,
                    CODE, "original canonical segment/registry mapping refused")
            return dict(facts, withinCutoff=int(entry["effectiveAt"]) <= int(cutoff),
                        registeredHolderIsBuyer=holder == binding.position.payer,
                        atomicSettlementAuthority=False, fundsDispatched=False,
                        holderWritten=False, finalityWritten=False,
                        observation="READ_ONLY_JOIN")
        require(False, CODE, "Oracle projection changed during both bounded reads")
