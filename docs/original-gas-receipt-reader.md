# Original RPC gas receipt reader

This initial composition uses an injected existing authenticated JSON-RPC transport and the prior ReceiptGasObserver. It adds no endpoint, credentials, transport client, runtime, database or wallet authority.

The original transport contract is synchronous original_rpc(method, parameters) returning the exact JSON bytes of the authenticated result value. The installed transport owns bounded request timeouts, JSON-RPC version/ID and error validation, provider authenticity and exact extraction. A callback is not proof that the transport exists or is correctly installed. No caller-supplied URL, alternate provider or retry is accepted.

A non-null observation makes at most seven read-only calls: chain ID, original transaction receipt, finalized head, canonical receipt block by number, identical receipt readback, canonical block readback, and chain ID readback. It requires Sepolia, a receipt no later than the finalized head, and a stable canonical block identity. Changed raw receipt bytes refuse conservatively even if a provider merely reformats equivalent JSON. Null returns unknown after the second call and cannot become zero-cost settlement. Unfinalized, unavailable, wrong-chain and changed-block observations retain the existing reservation; this reader does not release anything.

The original attempt verifier then receives all raw read results and the exact receipt evidence. It must verify the original native wallet journal attempt/transaction/proof binding and authenticated transport/finality policy. Numeric block ordering alone is not cryptographic proof of ancestry. The original trusted node and verifier establish that relationship. No finality setting is guessed or bypassed; unsupported finalized-tag providers refuse rather than downgrade to latest. A reorg after accepted settlement remains the original journal coordinator's recovery responsibility.

The returned observation is still evidence input for the original settlement coordinator. There is no automatic reconcile, debit, unfreeze, signing, send, Oracle write or second financial journal. Existing financial deduplication and upper-bound controls remain mandatory. Real adapter installation, journal association and end-to-end wallet accounting remain UNBOUND/NOT_RUN.

Protocol references: [Ethereum JSON-RPC](https://ethereum.org/en/developers/docs/apis/json-rpc/) defines chain ID, transaction receipts, block-by-number and finalized block tags. This module calls only those read methods; no actual provider was queried during initial authoring.

Validation input: eight authored synthetic-sequence unittest methods, NOT_RUN. Proposed validation-owner command: python -m unittest integration.test_original_gas_receipt_reader -v. No product import, compile, test, CI, chain, wallet or deployment acceptance is claimed. This branch stacks on the pinned receipt observer implementation; its helper contract requires joint version review.
