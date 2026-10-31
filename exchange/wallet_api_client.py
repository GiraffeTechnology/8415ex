"""Original Wallet HTTP auth/task client; no discovery or signer/RPC defaults."""
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from http.cookiejar import CookieJar
import http.client
import json
import re
import ssl
import time
from threading import RLock
from urllib.parse import urlsplit
from urllib.request import Request
from .wallet_execution_attempts import WalletExecutionAttempts


class WalletAPIRefused(ValueError):
    """Only non-secret codes cross this error boundary."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise WalletAPIRefused("EX_WALLET_JSON_REFUSED")
        result[key] = value
    return result


def _bad_number(value):
    raise WalletAPIRefused("EX_WALLET_JSON_REFUSED")


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._operation_lock:
            return method(self, *args, **kwargs)
    return call


class WalletAPIClient:
    """One private cookie/CSRF session for an existing registered EX actor.

    The caller supplies the existing login-message signer. There is no key
    loader, transaction-signer fallback, account provisioning or scope widening.
    Native policy/child construction and atomic execution remain server-owned.
    """
    _BOUND_CHAIN = "11155111"

    _FIELDS = {
        "prepare": {"policy"},
        "authorize": {"challengeId", "taskDigest", "executorDigest", "observationPolicyDigest", "code"},
        "status": {"taskDigest"}, "resume": {"taskDigest"},
        "reserve": {"taskDigest", "child", "expectedBudgetRevision"},
        "execute": {"taskDigest", "operationId", "childDigest", "expectedBudgetRevision"},
        "recover": {"taskDigest", "operationId", "childDigest", "expectedBudgetRevision"},
        "observe": {"taskDigest", "operationId", "childDigest", "expectedBudgetRevision"},
        "observe-replacement": {"taskDigest", "operationId", "childDigest", "expectedBudgetRevision", "replacementHash"},
    }

    def __init__(self, origin, tenant, account, chain_id, *, clock_ms=None,
                 timeout_seconds=10, allow_loopback_http=False, execution_attempts=None, base_path=""):
        # V3 tenant routing is explicit deployment configuration, not discovery.
        # The signing origin and durable operation identity remain unchanged.
        if type(base_path) is not str or (base_path != "" and
                (type(tenant) is not str or tenant in ("v2", "v3", "auth", "api", "web", "assets", "dist", "docs", "scripts", "server",
                    "tests", "config", "login", "logout", "register", "about", "settings", "default",
                    "__proto__", "constructor", "prototype") or base_path != "/" + tenant)):
            raise WalletAPIRefused("EX_WALLET_BASE_PATH_REFUSED")
        if type(origin) is not str:
            raise WalletAPIRefused("EX_WALLET_BINDING_REFUSED")
        url = urlsplit(origin)
        loopback = url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
        if (url.username or url.password or not url.hostname or url.path or url.query or url.fragment
                or not (url.scheme == "https" or (allow_loopback_http is True and loopback))
                or any(c in origin for c in "\r\n\t")
                or type(tenant) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", tenant)
                or type(account) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{40}", account)
                or int(account, 16) == 0 or str(chain_id) != self._BOUND_CHAIN
                or type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30):
            raise WalletAPIRefused("EX_WALLET_BINDING_REFUSED")
        self._origin, self._tenant = origin, tenant
        self._base_path = base_path
        self._account, self._chain = account.lower(), str(chain_id)
        self._clock = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._timeout = timeout_seconds
        self._jar = CookieJar()
        self._url = url
        self._tls = ssl.create_default_context()
        self._csrf, self._session = None, None
        self._used_challenges, self._uncertain = set(), set()
        self._operation_lock = RLock()
        if execution_attempts is not None and not isinstance(execution_attempts, WalletExecutionAttempts):
            raise WalletAPIRefused("EX_WALLET_ATTEMPT_STORE_REFUSED")
        self._execution_attempts = execution_attempts

    def _reset(self):
        self._jar.clear()
        self._csrf, self._session = None, None

    def _request(self, path, body=None):
        if path not in {"bootstrap", "challenge", "proof", "session", "logout"} and not (
                path.startswith("tasks/") and path[6:] in self._FIELDS):
            raise WalletAPIRefused("EX_WALLET_ROUTE_REFUSED")
        headers = {"Origin": self._origin, "X-Wallet-Tenant": self._tenant,
                   "Accept": "application/json", "Accept-Encoding": "identity"}
        if self._csrf is not None:
            headers["X-Wallet-CSRF"] = self._csrf
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
            if len(data) > 65536:
                raise WalletAPIRefused("EX_WALLET_REQUEST_TOO_LARGE")
            headers["Content-Type"] = "application/json"
        request_path = self._base_path + "/auth/" + path
        req = Request(self._origin + request_path, data=data, headers=headers,
                      method="GET" if body is None else "POST")
        # One decreasing socket-phase/body budget, not one new timeout per
        # packet. The platform resolver must provide its existing DNS bound.
        deadline = time.monotonic() + self._timeout
        connection = response = None

        def remaining():
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise WalletAPIRefused("EX_WALLET_TRANSPORT_DEADLINE")
            return budget

        try:
            if self._url.scheme == "https":
                connection = http.client.HTTPSConnection(
                    self._url.hostname, self._url.port, timeout=remaining(), context=self._tls)
            else:
                connection = http.client.HTTPConnection(
                    self._url.hostname, self._url.port, timeout=remaining())
            connection.connect()
            sock = connection.sock
            if sock is None:
                raise WalletAPIRefused("EX_WALLET_TRANSPORT_UNAVAILABLE")
            # Keep the original CookieJar's URL/path/domain/expiry rules.
            # No environment proxy, redirect, new endpoint or retry exists.
            self._jar.add_cookie_header(req)
            sock.settimeout(remaining())
            connection.request(req.get_method(), request_path,
                               body=data, headers=dict(req.header_items()))
            sock.settimeout(remaining())
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise WalletAPIRefused("EX_WALLET_REDIRECT_REFUSED")
            if (response.headers.get_content_type() != "application/json"
                    or response.headers.get_content_charset() not in (None, "utf-8")
                    or response.getheader("Content-Encoding", "identity").lower() != "identity"):
                raise WalletAPIRefused("EX_WALLET_RESPONSE_REFUSED")
            lengths = response.headers.get_all("Content-Length", [])
            transfer = response.getheader("Transfer-Encoding")
            if (len(lengths) > 1 or (lengths and transfer)
                    or (transfer is not None and transfer.lower() != "chunked")):
                raise WalletAPIRefused("EX_WALLET_RESPONSE_FRAMING_REFUSED")
            expected = None
            if lengths:
                if re.fullmatch(r"[0-9]{1,10}", lengths[0]) is None:
                    raise WalletAPIRefused("EX_WALLET_RESPONSE_FRAMING_REFUSED")
                expected = int(lengths[0])
                if expected > 65536:
                    raise WalletAPIRefused("EX_WALLET_RESPONSE_TOO_LARGE")
            chunks, size = [], 0
            while expected is None or size < expected:
                sock.settimeout(remaining())
                chunk = response.read1(min(4096, 65537 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > 65536:
                    raise WalletAPIRefused("EX_WALLET_RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            if expected is not None and size != expected:
                raise WalletAPIRefused("EX_WALLET_RESPONSE_TRUNCATED")
            remaining()
            result = json.loads(b"".join(chunks).decode("utf-8"), object_pairs_hook=_pairs,
                                parse_float=_bad_number, parse_constant=_bad_number)
            if type(result) is not dict:
                raise WalletAPIRefused("EX_WALLET_RESPONSE_REFUSED")
            # A partial/invalid response must not replace the prior cookies.
            self._jar.extract_cookies(response, req)
            if response.status != 200:
                code = result.get("error")
                refusal = WalletAPIRefused(code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                                           else "EX_WALLET_REQUEST_REFUSED")
                refusal.http_status = response.status
                raise refusal
            return result
        except WalletAPIRefused:
            raise
        except Exception:
            raise WalletAPIRefused("EX_WALLET_TRANSPORT_UNAVAILABLE") from None
        finally:
            for resource in (response, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass

    def _bound(self, row, *, challenge=False):
        now = self._clock()
        if (type(row) is not dict or row.get("origin") != self._origin or row.get("tenant") != self._tenant
                or type(row.get("account")) is not str or row["account"].lower() != self._account
                or row.get("chainId") != self._chain
                or type(row.get("issuedAt")) is not int or type(row.get("expiresAt")) is not int
                or type(now) is not int or not row["issuedAt"] <= now < row["expiresAt"]
                or row["expiresAt"] - row["issuedAt"] > (120000 if challenge else 900000)
                or type(row.get("id")) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{43}", row["id"])):
            raise WalletAPIRefused("EX_WALLET_SESSION_BINDING_REFUSED")
        if not challenge and (row.get("kind") != "wallet" or type(row.get("csrf")) is not str
                              or not re.fullmatch(r"[A-Za-z0-9_-]{43}", row["csrf"])):
            raise WalletAPIRefused("EX_WALLET_SESSION_BINDING_REFUSED")

    def _login_message(self, row):
        self._bound(row, challenge=True)
        if row.get("method") != "wallet" or type(row.get("nonce")) is not str or not re.fullmatch(r"[A-Za-z0-9]{1,128}", row["nonce"]):
            raise WalletAPIRefused("EX_WALLET_CHALLENGE_REFUSED")
        iso = lambda value: datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        expected = (self._origin + " wants you to sign in with your Ethereum account:\n" + row["account"]
            + "\n\nLog in to 8415wallet to view assets and history. This does not authorize a transaction or standing access."
            + "\n\nURI: " + self._origin + "\nVersion: 1\nChain ID: " + self._chain
            + "\nNonce: " + row["nonce"] + "\nIssued At: " + iso(row["issuedAt"])
            + "\nExpiration Time: " + iso(row["expiresAt"])
            + "\nResources:\n- urn:8415wallet:tenant:" + self._tenant
            + "\n- urn:8415wallet:purpose:login\n- urn:8415wallet:request:" + row["id"])
        if row.get("message") != expected or row["id"] in self._used_challenges:
            raise WalletAPIRefused("EX_WALLET_CHALLENGE_REFUSED")
        return expected

    @_serialized
    def login(self, sign_login_message):
        if not callable(sign_login_message):
            raise WalletAPIRefused("EX_WALLET_MESSAGE_SIGNER_REQUIRED")
        return self._authenticate(lambda challenge, message:
                                  sign_login_message(message, self._account, self._chain))

    @_serialized
    def login_native(self, sign_login_challenge):
        """Use the original Wallet's login-purpose challenge signer.

        The native Wallet retains custody and validates its complete challenge.
        This consumer passes no key, arbitrary message, session or task grant.
        """
        if not callable(sign_login_challenge):
            raise WalletAPIRefused("EX_WALLET_MESSAGE_SIGNER_REQUIRED")

        def sign(challenge, message):
            fields = {"origin", "tenant", "account", "chainId", "nonce",
                      "issuedAt", "expiresAt", "id", "method", "message"}
            if (set(challenge) != fields
                    or re.fullmatch(r"[A-Za-z0-9]{8,64}", challenge["nonce"]) is None):
                raise WalletAPIRefused("EX_WALLET_CHALLENGE_REFUSED")
            try:
                proof = sign_login_challenge(challenge)
            except Exception as error:
                if str(error) in ("NATIVE_LOGIN_CANCELLED", "LOGIN_CANCELLED"):
                    raise WalletAPIRefused("EX_WALLET_LOGIN_CANCELLED") from None
                raise WalletAPIRefused("EX_WALLET_NATIVE_LOGIN_REFUSED") from None
            if type(proof) is not dict or set(proof) != {"signature"}:
                raise WalletAPIRefused("EX_WALLET_NATIVE_LOGIN_RESPONSE_REFUSED")
            return proof["signature"]

        return self._authenticate(sign)

    def _authenticate(self, sign):
        self._reset()
        try:
            boot = self._request("bootstrap")
            if type(boot.get("csrf")) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{43}", boot["csrf"]):
                raise WalletAPIRefused("EX_WALLET_CSRF_REFUSED")
            self._csrf = boot["csrf"]
            challenge = self._request("challenge", {"method": "wallet", "account": self._account, "chainId": self._chain})
            message = self._login_message(challenge)
            self._used_challenges.add(challenge["id"])
            signature = sign(deepcopy(challenge), message)
            self._bound(challenge, challenge=True)
            if type(signature) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{130}", signature):
                raise WalletAPIRefused("EX_WALLET_LOGIN_SIGNATURE_REFUSED")
            session = self._request("proof", {"account": self._account, "chainId": self._chain,
                                    "id": challenge["id"], "signature": signature})
            self._bound(session)
            self._csrf, self._session = session["csrf"], deepcopy(session)
            return self.session()
        except WalletAPIRefused:
            self._reset()
            raise
        except Exception:
            self._reset()
            raise WalletAPIRefused("EX_WALLET_LOGIN_REFUSED") from None

    @_serialized
    def session(self):
        if self._session is None:
            raise WalletAPIRefused("EX_WALLET_LOGIN_REQUIRED")
        try:
            row = self._request("session")
            self._bound(row)
            if row != self._session:
                raise WalletAPIRefused("EX_WALLET_SESSION_CHANGED")
            return {"authenticated": True, "chainId": self._chain}
        except WalletAPIRefused:
            self._reset()
            raise
        except Exception:
            self._reset()
            raise WalletAPIRefused("EX_WALLET_SESSION_CHANGED") from None

    @_serialized
    def task(self, action, payload):
        if action not in self._FIELDS or type(payload) is not dict:
            raise WalletAPIRefused("EX_WALLET_TASK_FIELDS_REFUSED")
        request = deepcopy(payload)
        if set(request) != self._FIELDS[action]:
            raise WalletAPIRefused("EX_WALLET_TASK_FIELDS_REFUSED")
        if action == "execute" and self._execution_attempts is None:
            # A process-local uncertain set cannot prevent a restart resend.
            # The host must bind its existing dedicated durable attempt store;
            # never silently create a production DB or select a fallback path.
            raise WalletAPIRefused("EX_WALLET_DURABLE_ATTEMPT_STORE_REQUIRED")
        self.session()
        operation = (request.get("taskDigest"), request.get("operationId"))
        if action == "execute" and operation in self._uncertain:
            raise WalletAPIRefused("EX_WALLET_UNKNOWN_RECONCILE_FIRST")
        if action == "execute" and self._execution_attempts is not None:
            try:
                claimed = self._execution_attempts.claim({"origin": self._origin,
                    "tenant": self._tenant, "account": self._account, "chainId": self._chain}, request)
            except Exception:
                raise WalletAPIRefused("EX_WALLET_ATTEMPT_STORE_UNAVAILABLE") from None
            if claimed is not True:
                raise WalletAPIRefused("EX_WALLET_ATTEMPT_RECONCILE_FIRST")
        try:
            return self._request("tasks/" + action, request)
        except Exception as error:
            if action == "execute":
                self._uncertain.add(operation)
                refused = WalletAPIRefused("EX_WALLET_EXECUTION_OUTCOME_UNKNOWN")
                if isinstance(error, WalletAPIRefused):
                    refused.source_code = str(error)
                    refused.http_status = getattr(error, "http_status", None)
                raise refused from None
            raise

    @_serialized
    def logout(self):
        try:
            if self._csrf is not None:
                self._request("logout", {})
        finally:
            self._reset()

