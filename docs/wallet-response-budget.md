# Wallet response read budget

The original Wallet HTTP client previously called one buffered `read(65537)`.
A peer could keep that read alive by returning bytes more frequently than the
socket inactivity timeout. The client now uses a decreasing monotonic budget
across socket phases and incremental `read1` body reads, retaining the configured
timeout and 64 KiB maximum. It rejects conflicting/duplicate framing, oversized
declared lengths, truncated bodies and non-UTF-8 JSON responses.

This is a socket-phase and incremental-body bound, not a process-wide DNS or
arbitrary HTTP parser deadline: platform resolution must retain its existing
host bound, and a library operation already in progress retains its socket
inactivity bound. No new background financial worker or automatic retry exists.

The existing origin, Sepolia account/tenant binding, cookie jar rules, CSRF
rotation, login message checks, task fields and durable execute claim remain.
TLS verification stays enabled, proxies and redirects remain absent, and cookies
are extracted only after a complete valid JSON object has been read. An uncertain
execute result keeps the original durable/process-local reconciliation guard;
a transport failure never establishes authenticated absence or permits resend.

Requirements: EX-AUTH-01, EX-INV-04, EX-NFR-09; original native integration and
unknown-result recovery. This is a client transport change, not a new human
approval, Wallet readiness requirement, native execution port or authority grant.

The new synthetic fixtures cover a dripping body, duplicate/ambiguous framing,
oversize/truncation, valid fixed/chunked JSON and no-resend after an uncertain
execute. Run them with the existing Wallet client suite on approved Linux CI.
Definitions are NOT_RUN by the author. They do not establish installed Wallet,
DNS/TLS/provider, transaction or full EX acceptance.
