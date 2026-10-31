"""Market-only bounded browser reference refresh and response policy."""
import base64
import hashlib

REFERENCE_SCRIPT = r"""(() => {
  "use strict";
  const interval = 60000;
  const limit = 65536;
  let timer = null, active = null, stopped = false;
  const panel = () => document.getElementById("commodity-reference");
  const schedule = () => {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(refresh, interval);
  };
  async function refresh() {
    if (stopped || document.hidden || active || !panel()) return;
    const controller = new AbortController();
    active = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const url = new URL(window.location.href);
      url.hash = "";
      url.searchParams.set("reference", "1");
      const response = await fetch(url.href, {
        method: "GET", cache: "no-store", credentials: "omit",
        redirect: "error", signal: controller.signal
      });
      if (!response.ok || response.url !== url.href ||
          response.headers.get("content-type")?.split(";")[0].trim() !== "text/html" ||
          !response.body) throw new Error("reference read unavailable");
      const reader = response.body.getReader();
      const chunks = [];
      let total = 0;
      try {
        while (true) {
          const part = await reader.read();
          if (part.done) break;
          total += part.value.byteLength;
          if (total > limit) throw new Error("reference response exceeds bound");
          chunks.push(part.value);
        }
      } finally {
        await reader.cancel().catch(() => {});
      }
      const raw = new Uint8Array(total);
      let offset = 0;
      for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.byteLength; }
      const html = new TextDecoder("utf-8", {fatal: true}).decode(raw);
      const parsed = new DOMParser().parseFromString(html, "text/html");
      if (parsed.body.children.length !== 1 || parsed.head.children.length)
        throw new Error("reference fragment differs");
      const next = parsed.body.firstElementChild;
      if (next.tagName !== "SECTION" || next.id !== "commodity-reference")
        throw new Error("reference panel differs");
      const tags = new Set(["SECTION", "H2", "P", "DL", "DT", "DD", "DETAILS", "SUMMARY"]);
      const attrs = new Set(["id", "class", "data-reference-status",
        "data-browser-error", "data-unavailable", "hidden", "aria-live"]);
      for (const node of [next, ...next.querySelectorAll("*")]) {
        if (!tags.has(node.tagName) ||
            [...node.attributes].some(attribute => !attrs.has(attribute.name)))
          throw new Error("reference fragment content refused");
      }
      if (!stopped && panel()) {
        const expanded = panel().querySelector("details")?.open === true;
        const disclosure = next.querySelector?.("details");
        if (disclosure) disclosure.open = expanded;
        panel().replaceWith(document.importNode(next, true));
      }
    } catch (_) {
      const previous = panel();
      if (!stopped && previous) {
        const error = previous.querySelector("[data-browser-error]");
        if (error) error.hidden = false;
      }
    } finally {
      clearTimeout(timeout);
      active = null;
      schedule();
    }
  }
  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (!document.hidden && !stopped) refresh();
  });
  window.addEventListener("pagehide", () => {
    stopped = true;
    clearTimeout(timer);
    if (active) active.abort();
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) { stopped = false; refresh(); }
  });
  schedule();
})();"""

SCRIPT_HASH = base64.b64encode(hashlib.sha256(REFERENCE_SCRIPT.encode()).digest()).decode()
MARKET_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
    "script-src 'sha256-" + SCRIPT_HASH + "'; connect-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


def send_market_response(handler, body):
    """Send only the original market document with its exact script hash."""
    raw = body.encode("utf-8")
    handler.send_response(200)
    for name, value in (
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(raw))), ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", MARKET_CSP),
    ):
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(raw)
