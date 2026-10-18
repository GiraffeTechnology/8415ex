# Discover UNKNOWN operations after restart

The durable journal's existing single-operation enquiry requires an operation
identity. After restarting, the application also needs to discover persisted
UNKNOWN identities without relying on its previous in-memory receipt objects.

The bounded internal recovery reader pages through the existing dedicated EX
claim store, validates each selected scope against its receipt index, and calls
the original read-only enquiry. It accepts no dispatch callback. A terminal local
claim is excluded; an unavailable native enquiry leaves UNKNOWN and does not
prevent other original operations in that page from being read. Error details
are not copied into the public result.

The cursor is not an authorization or permanent watermark. Each later complete
sweep must start at the beginning because new identifiers can sort before an
older cursor. No timer, HTTP endpoint or background worker is installed here.
The application must authenticate the reader and bind the original enquiry.

Five authored regression definitions use real temporary SQLite files and
synthetic native replies. Status is NOT_RUN pending established approved remote
Linux QA. This adds discovery for original-operation reconciliation, not full
exchange state or queue reconstruction, a financial journal, automatic resend,
refund, signing, deployment or live chain acceptance.
