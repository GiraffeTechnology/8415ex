"""Bounded read-only HTTP transport for the original Oracle application API.

No connection is made on import or construction. The explicit origin must come
from the existing deployment configuration. TLS certificate checks stay enabled.
"""
import http.client
import json
import re
import ssl
import time
from urllib.parse import urlsplit


class OracleHTTPRefused(ValueError):
    pass


def _require(ok, code):
    if not ok:
        raise OracleHTTPRefused(code)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "ORACLE_HTTP_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _no_noninteger_number(value):
    raise OracleHTTPRefused("ORACLE_HTTP_NONINTEGER_JSON_NUMBER")


class OracleHTTPTransport:
    """GET only; no redirects, retries, cookies, credentials or global proxy changes.

    Connection setup is deferred until __call__. Socket phases use a decreasing
    monotonic budget. Platform DNS resolution is synchronous; the host resolver
    must supply its existing bound. This is not a process-wide DNS deadline.
    """
    MAX_BYTES = 65536
    ROUTE = re.compile(r"\A/v1/oracle/projection/(0|[1-9][0-9]{0,77})"
                       r"(?:/(entry/version|holder/as-of|finality/as-of)"
                       r"/(0|[1-9][0-9]{0,19}))?\Z")

    def __init__(self, origin, timeout_ms=5000):
        _require(type(origin) is str and len(origin) <= 2048 and origin.isascii()
                 and not any(ord(c) <= 32 or ord(c) == 127 for c in origin),
                 "ORACLE_HTTP_ORIGIN_REFUSED")
        try:
            url = urlsplit(origin)
            host, port = url.hostname, url.port
        except ValueError:
            raise OracleHTTPRefused("ORACLE_HTTP_ORIGIN_REFUSED") from None
        _require(url.scheme in ("http", "https") and host is not None
                 and url.username is None and url.password is None
                 and not url.query and not url.fragment and "%" not in host
                 and (port is None or 1 <= port <= 65535), "ORACLE_HTTP_ORIGIN_REFUSED")
        _require(url.scheme == "https" or host in ("localhost", "127.0.0.1", "::1"),
                 "ORACLE_HTTP_TLS_REQUIRED")
        prefix = url.path.rstrip("/")
        _require((url.path in ("", "/") or url.path in (prefix, prefix + "/"))
                 and re.fullmatch(r"(?:/[A-Za-z0-9._~-]+)*", prefix) is not None
                 and all(part not in (".", "..") for part in prefix.split("/")),
                 "ORACLE_HTTP_ORIGIN_PATH_REFUSED")
        _require(type(timeout_ms) is int and 1 <= timeout_ms <= 30000,
                 "ORACLE_HTTP_TIMEOUT_REFUSED")
        self._scheme, self._host, self._port = url.scheme, host, port
        self._prefix, self._timeout = prefix, timeout_ms / 1000

    def __call__(self, method, path):
        _require(method == "GET" and type(method) is str and type(path) is str,
                 "ORACLE_HTTP_READ_ONLY")
        match = self.ROUTE.fullmatch(path)
        _require(match is not None and int(match[1]) < 2 ** 256
                 and (match[3] is None or int(match[3]) < 2 ** 64)
                 and (match[2] != "entry/version" or match[3] != "0"),
                 "ORACLE_HTTP_ROUTE_REFUSED")
        deadline = time.monotonic() + self._timeout
        connection = response = None

        def remaining():
            value = deadline - time.monotonic()
            _require(value > 0, "ORACLE_HTTP_DEADLINE")
            return value

        try:
            if self._scheme == "https":
                connection = http.client.HTTPSConnection(
                    self._host, self._port, timeout=remaining(), context=ssl.create_default_context())
            else:
                connection = http.client.HTTPConnection(self._host, self._port, timeout=remaining())
            connection.connect()
            sock = connection.sock
            _require(sock is not None, "ORACLE_HTTP_CONNECTION_REFUSED")
            sock.settimeout(remaining())
            connection.request("GET", self._prefix + path,
                               headers={"Accept": "application/json", "Accept-Encoding": "identity"})
            sock.settimeout(remaining())
            response = connection.getresponse()
            _require(type(response.status) is int and not 300 <= response.status < 400,
                     "ORACLE_HTTP_REDIRECT_REFUSED")
            _require(response.headers.get_content_type() == "application/json"
                     and response.headers.get_content_charset() in (None, "utf-8"),
                     "ORACLE_HTTP_CONTENT_TYPE_REFUSED")
            _require(response.getheader("Content-Encoding", "identity").lower() == "identity",
                     "ORACLE_HTTP_CONTENT_ENCODING_REFUSED")
            lengths = response.headers.get_all("Content-Length", [])
            transfer = response.getheader("Transfer-Encoding")
            _require(len(lengths) <= 1 and not (lengths and transfer)
                     and (transfer is None or transfer.lower() == "chunked"),
                     "ORACLE_HTTP_FRAMING_REFUSED")
            expected = None
            if lengths:
                text = lengths[0]
                _require(re.fullmatch(r"[0-9]{1,10}", text) is not None
                         and int(text) <= self.MAX_BYTES, "ORACLE_HTTP_LENGTH_REFUSED")
                expected = int(text)
            chunks, size = [], 0
            while expected is None or size < expected:
                sock.settimeout(remaining())
                chunk = response.read1(min(4096, self.MAX_BYTES - size + 1))
                _require(type(chunk) is bytes, "ORACLE_HTTP_BODY_REFUSED")
                if not chunk:
                    break
                size += len(chunk)
                _require(size <= self.MAX_BYTES, "ORACLE_HTTP_BODY_TOO_LARGE")
                chunks.append(chunk)
            _require(expected is None or size == expected, "ORACLE_HTTP_TRUNCATED_BODY")
            remaining()
            body = json.loads(b"".join(chunks).decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique, parse_float=_no_noninteger_number,
                              parse_constant=_no_noninteger_number)
            _require(type(body) is dict, "ORACLE_HTTP_BODY_REFUSED")
            return response.status, body
        except OracleHTTPRefused:
            raise
        except Exception:
            # No URL, raw body, TLS details, credentials or private runtime
            # exception text is copied into a public product error.
            raise OracleHTTPRefused("ORACLE_HTTP_UNAVAILABLE_OR_MALFORMED") from None
        finally:
            for resource in (response, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass
