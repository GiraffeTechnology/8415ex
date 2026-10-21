# Browser refresh of the original reference panel

The market page now refreshes its reference panel without replacing NFT cards,
navigation, search input or other page state. The existing `/market` route
accepts `reference=1` with the same supported locale and bounded search query,
returning only the original server-rendered reference section. Other catalogue
JSON responses and read-only command boundaries remain unchanged. No new proxy
route, port, external browser data source or trade request is introduced.

The browser waits one minute between completed reads. This is page-observation
cadence, not provider supply cadence: a fragment request calls only the existing
feed snapshot, never an external provider refresh. Source and fetch timestamps
come from the original feed and do not advance just because the page reads
them again. Fresh, stale, unavailable and unknown states retain their original
six-language rendering and source evidence.

Only one fragment request can run at a time. It has a ten-second abort timeout,
a 64 KiB response bound, same-URL/status/MIME checks and strict allowed fragment
elements/attributes. Hidden pages do not start another read. Page exit cancels
the browser read; a restored page resumes. A failed or refused read preserves
the previous observation and shows a localized page-refresh failure message.
No browser error becomes a fake zero or an external source success.

The market document alone receives a CSP allowing its exact inline-script
SHA-256, same-origin reads and existing images. It allows no arbitrary inline
scripts, external scripts, frames or foreign requests. All other HTML/JSON
responses retain their original restrictive policy. Reference fragments contain
no executable markup; source text remains escaped before rendering.

Acceptance mapping: T-71 / EX-PRICE-01 connects source changes to the current
page; T-72 / EX-PRICE-02 through EX-PRICE-04 retains source/fetch precision,
failure/recovery and separation from NFT prices and financial execution.
Ten original-server HTTP regression definitions are included and have not been
run by the source author. Browser lifecycle execution, actual ongoing source
changes and production serving remain separate acceptance evidence.
