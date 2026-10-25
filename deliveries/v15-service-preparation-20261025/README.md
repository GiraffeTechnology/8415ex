# V1.5 incomplete service-preparation candidate

**NOT PRODUCTION READY. DO NOT MERGE THE V1.5 DEVELOPMENT INTO MAIN.**
This is an offline service-preparation bundle, not a completed installation or native acceptance result. Authenticated native proof verification, the original authorized task-policy journal/resolver, Oracle bindings and the real host integration remain incomplete. See [gaps](SERVICE-GAPS.json) and [installation/readiness instructions](INSTALL.md).

## Download and identity

- [Full offline service bundle](8415ex-v15-service-candidate.tar)
- [SHA256SUMS](SHA256SUMS)
- Size: 1,843,200 bytes
- SHA-256: `d1392a7084780693dd27d68cc47957a952addcb5e23084936a4e2c546d3c301e`
- Embedded complete source content tree: `dbb6eb8381be6814ee6881484642e4a6565d2ab6`
- Embedded build-source commit identifier: `8fababe4febc344ad8f07db54a44cc2c0714bedd`. This identifies the local build input; its commit/history is **not** published as the repository branch head.
- Retained full V1.5 PRD SHA-256: `e5124bb30d408ae6ce8bcaba7c1ba6d14eda2a461c25e0c9c7202410278856c6` (123 requirements, T-01..96, six continuous stages).
- Inputs: isolated V1.5 `764faeea7b9c1f638db8a5b61caaadf3a60f4428`, valid main changes through `c74f92406393ee1acc30920dbd4ab819aa021ad6`, additional complete same-store core and service-preparation changes.

The archive includes 698 source files, the offline installer, typed external host schema, full source tests and explicit readiness gaps. It contains no Wallet implementation, credentials or Git author metadata. It installs only into a new version directory and does not start a service, initialize/migrate state, configure credentials or execute transactions.

## Actual local evidence

The prior integrated source passed 734 domain and 1,497 integration tests. The corrected scenario source passed all 628 scenario tests. The final service/composition/package/scalar affected aggregate passed 32 tests. The CI evidence fixture and smoke fixture passed 20 and 9 tests separately. These are **local test results on their recorded source versions**, not a claim that every suite ran on this artifact's final tree or that GitHub CI is green.

The final archive was built twice byte-identically; all inner checksums and the fresh installed 698-file tree verified. Missing-host readiness failed closed. Real-code EX-to-Wallet HTTP login/session/logout interoperability passed for separate Sepolia and Hoodi sessions against synthetic in-memory state; this is not genuine runtime/store/chain acceptance.

**NOT VERIFIED / NOT RUN:** actual served SHA, authoritative runtime/store binding, authenticated native financial paths, N06/X02/X03/X04 real-runtime evidence and deployed browser recovery. No production deployment or real transaction was performed. PR #166's isolation/merge hold remains unchanged.
