"""Bounded GET readback of declared health and exact approved UI asset bytes.

HTTP agreement is not provider, installed-source or business attestation.
This module neither deploys a service nor selects any infrastructure inputs.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ASSETS = {
    "soy.png": "image/png", "ore.png": "image/png", "copper.png": "image/png",
    "cube.svg": "image/svg+xml", "search.svg": "image/svg+xml",
    "sparkline.svg": "image/svg+xml", "sparkline-stale.svg": "image/svg+xml",
}
HEALTH_LIMIT = 16_384
ASSET_LIMIT = 262_144


class ReadbackRefused(ValueError):
    """A fixed refusal code; never echo an untrusted response or credential."""


def require(condition, code):
    if not condition:
        raise ReadbackRefused(code)


def origin_value(value):
    require(type(value) is str, "ORIGIN_REQUIRED")
    parsed = urlsplit(value)
    require(parsed.scheme in ("http", "https") and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not parsed.query and not parsed.fragment
            and parsed.path in ("", "/") and not any(c.isspace() for c in value),
            "ORIGIN_REFUSED")
    try:
        parsed.port
    except ValueError:
        raise ReadbackRefused("ORIGIN_REFUSED") from None
    return value.rstrip("/")


@dataclass(frozen=True)
class Observation:
    status: int
    headers: dict
    body: bytes
    final_url: str


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpGet:
    def __init__(self, origin, *, timeout):
        self.origin = origin_value(origin)
        require(type(timeout) in (int, float) and 0 < timeout <= 60,
                "TIMEOUT_REFUSED")
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    def __call__(self, path, limit):
        require(path == "/healthz" or path in {"/assets/" + n for n in ASSETS},
                "READ_PATH_REFUSED")
        require(type(limit) is int and 0 < limit <= ASSET_LIMIT, "READ_LIMIT_REFUSED")
        request = Request(self.origin + path, method="GET", headers={
            "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                headers = {}
                for key, value in response.headers.items():
                    require(key.lower() not in headers, "DUPLICATE_HEADER")
                    headers[key.lower()] = value
                return Observation(response.status, headers,
                                   response.read(limit + 1), response.geturl())
        except HTTPError as error:
            error.close()
            raise ReadbackRefused("HTTP_STATUS_REFUSED") from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def invalid_constant(value):
    raise ReadbackRefused("NONSTANDARD_JSON_NUMBER")


def checked_body(observation, origin, path, limit, content_type):
    require(type(observation) is Observation, "OBSERVATION_REQUIRED")
    require(type(observation.status) is int and observation.status == 200,
            "HTTP_STATUS_REFUSED")
    require(observation.final_url == origin + path, "REDIRECT_OR_PATH_REFUSED")
    require(type(observation.body) is bytes and len(observation.body) <= limit,
            "BODY_SIZE_REFUSED")
    require(type(observation.headers) is dict, "HEADERS_REQUIRED")
    headers = {}
    for key, value in observation.headers.items():
        require(type(key) is str and type(value) is str, "HEADER_REFUSED")
        name = key.lower()
        require(name not in headers, "DUPLICATE_HEADER")
        headers[name] = value
    require(headers.get("content-type", "").split(";", 1)[0].strip().lower()
            == content_type, "CONTENT_TYPE_REFUSED")
    require(headers.get("content-encoding", "identity").lower() == "identity",
            "CONTENT_ENCODING_REFUSED")
    require("transfer-encoding" not in headers, "TRANSFER_ENCODING_REFUSED")
    length = headers.get("content-length", "")
    require(re.fullmatch(r"[0-9]{1,8}", length) is not None
            and int(length) == len(observation.body), "CONTENT_LENGTH_REFUSED")
    require("no-store" in {x.strip().lower() for x in
                           headers.get("cache-control", "").split(",")},
            "CACHE_POLICY_REFUSED")
    return observation.body


def verify(origin, expected_source, manifest, *, read):
    origin = origin_value(origin)
    require(type(expected_source) is dict and set(expected_source) == {"commit", "tree"},
            "SOURCE_REQUIRED")
    source = dict(expected_source)
    require(all(type(v) is str and re.fullmatch(r"[0-9a-f]{40}", v)
                for v in source.values()), "SOURCE_REQUIRED")
    require(type(manifest) is list and len(manifest) == len(ASSETS),
            "COMPLETE_ASSET_MANIFEST_REQUIRED")
    expected = {}
    for item in manifest:
        require(type(item) is dict and set(item) == {"path", "bytes", "sha256"},
                "ASSET_MANIFEST_REFUSED")
        name = item["path"]
        require(type(name) is str and name in {"/assets/" + n for n in ASSETS}
                and name not in expected, "ASSET_PATH_REFUSED")
        require(type(item["bytes"]) is int and 0 < item["bytes"] <= ASSET_LIMIT,
                "ASSET_SIZE_REFUSED")
        require(type(item["sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]),
                "ASSET_DIGEST_REFUSED")
        expected[name] = dict(item)

    raw = checked_body(read("/healthz", HEALTH_LIMIT), origin, "/healthz",
                       HEALTH_LIMIT, "application/json")
    try:
        health = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                            parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError):
        raise ReadbackRefused("HEALTH_JSON_REFUSED") from None
    require(type(health) is dict, "HEALTH_SCHEMA_REFUSED")
    require(health.get("schema") == "8415ex-http-health-observation/1"
            and health.get("httpProcess") == "serving", "HEALTH_SCHEMA_REFUSED")
    require(health.get("declaredSource") == source
            and health.get("sourceIdentity") == "DECLARED_ONLY", "DECLARED_SOURCE_MISMATCH")
    require(health.get("operationsREADY") == "NOT_VERIFIED"
            and all(health.get(k) == "NOT_EVALUATED" for k in
                    ("providerExecution", "chainAcceptance", "persistentRecovery")),
            "HEALTH_SCOPE_REFUSED")
    flags = health.get("configuredComponents")
    require(type(flags) is dict and set(flags) == {
        "commandGateway", "referenceFeed", "gasPage", "registrationSources"}
        and all(type(v) is bool for v in flags.values()), "COMPONENT_FLAGS_REFUSED")

    observed = []
    for path, item in sorted(expected.items()):
        body = checked_body(read(path, item["bytes"]), origin, path, item["bytes"],
                            ASSETS[path.rsplit("/", 1)[1]])
        digest = hashlib.sha256(body).hexdigest()
        require(len(body) == item["bytes"] and digest == item["sha256"],
                "ASSET_BYTES_MISMATCH")
        observed.append({"path": path, "bytes": len(body), "sha256": digest})
    return {"schema": "8415ex-served-resource-readback/1",
            "httpReadbackPassed": True, "declaredSource": source,
            "declaredSourceMatched": True, "healthSHA256": hashlib.sha256(raw).hexdigest(),
            "assets": observed, "assetCount": len(observed),
            "installedSourceIdentity": "NOT_VERIFIED", "providerExecution": "NOT_EVALUATED",
            "operationsREADY": "NOT_VERIFIED", "chainAcceptance": "NOT_EVALUATED",
            "uiJourneyAcceptance": "NOT_EVALUATED", "completeProductAcceptance": "OPEN"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read exact health and UI asset bytes; no deployment")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--timeout", required=True, type=float)
    args = parser.parse_args(argv)
    try:
        with open(args.asset_manifest, "rb") as stream:
            raw_manifest = stream.read(65_537)
            require(len(raw_manifest) <= 65_536, "MANIFEST_SIZE_REFUSED")
            manifest = json.loads(raw_manifest.decode("utf-8"),
                                  object_pairs_hook=unique_object,
                                  parse_constant=invalid_constant)
        result = verify(args.origin, {"commit": args.commit, "tree": args.tree}, manifest,
                        read=HttpGet(args.origin, timeout=args.timeout))
    except ReadbackRefused as error:
        print(json.dumps({"httpReadbackPassed": False, "reason": str(error),
                          "completeProductAcceptance": "OPEN"}, sort_keys=True))
        return 1
    except (OSError, ValueError):
        print(json.dumps({"httpReadbackPassed": False, "reason": "READBACK_INPUT_OR_TRANSPORT_REFUSED",
                          "completeProductAcceptance": "OPEN"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
