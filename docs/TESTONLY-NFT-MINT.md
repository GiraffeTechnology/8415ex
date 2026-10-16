# EX TESTONLY Sepolia NFT mint input

This is a separate test-only ERC721 issuer for valueless simulated warehouse-receipt data. It does not modify ArtFi production contracts, production evidence validators, the EX ledger, Oracle registration, payment settlement or any existing submitted module. No warehouse, institution, title or real-world value is asserted.

## Exact contract and dependency input

Contract: test-contracts/src/EXSepoliaTestNFT.sol:EXSepoliaTestNFT.
Constructor: constructor(address issuer_).
The immutable issuer must be the original approved EX project wallet controlled by the existing authorized signer. Zero address and deployment outside chain 11155111 refuse. TASK_ID is fixed as keccak256("8415EX"). There is no issuer setter, ownership transfer, proxy, delegatecall, arbitrary execution method or caller-selected mint recipient.

Fixed nonpayable mint ABI: mintSimulatedReceipt(bytes32 sourceHash,uint8 sourceKind) returns (uint256 tokenId).
Only msg.sender == issuer may call it, only on Sepolia. sourceHash is SHA-256 of exact original TESTONLY simulated document bytes, not a URL or a claim of production validation. Kinds 1, 2, 3 correspond to REG_DIRECT, REG_ELECTRONIC and REG_INTERMEDIARY simulated roles. Zero source hash, other kinds, reentrant mint and reuse of a source hash (even under another kind) refuse. The recipient is always issuer. Token IDs are assigned by the actual contract execution; do not put a future ID in a planned request.

The tokenURI is deterministic on-chain base64 JSON. It commits to the source hash, kind, task, chain, whole-receipt unit count and TESTONLY/non-production label. No external mutable URI or metadata setter is accepted. No secret is included. The source document itself is separately retained and hashed. Per-token ERC721 approval/transfer remains possible under the caller's original grant; setApprovalForAll always refuses, and no burn or physical pickup workflow exists. An ERC721 approval is not authority to bypass the server-side actor, asset or task scope.

The exact official OpenZeppelin dependency is pinned in test-contracts/dependencies.lock.json: v5.0.2 commit dbb6104ce834628e473d2173bbc9d47f81a9eec3. Only ERC721, Base64, Strings and their transitive official imports are used. No copied custom ERC721 implementation or forge-std is introduced. The Foundry configuration fixes Solidity 0.8.24, shanghai EVM, optimizer 200 and local out/cache, with offline=true. The approved build owner must supply the existing verified dependency input at test-contracts/lib/openzeppelin-contracts and existing approved compiler. The lock file is a source pin, not evidence that those inputs exist. No auto-install/download command or workflow change is included.

Protocol references: [OpenZeppelin ERC721](https://docs.openzeppelin.com/contracts/5.x/erc721) and [pinned implementation](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/dbb6104ce834628e473d2173bbc9d47f81a9eec3/contracts/token/ERC721/ERC721.sol).

## Build and deployment ownership

Proposed ordinary build/QA, by the existing validation owner in the existing approved Linux environment:
cd test-contracts
forge build --offline
forge test --offline

The author has not executed these commands. The initial environment check found no PATH command for forge/solc/node and no file at the three specific checked standard forge/solc paths; it is not a global absence claim. Original runtime holders recover an exact approved compiler reference. No tool installation, alternative environment or another project's application dependency is authorized by this package.

Expected compiler artifact path: test-contracts/out/EXSepoliaTestNFT.sol/EXSepoliaTestNFT.json. This is a future output locator, not an existing artifact. The build owner records actual compiler version, complete input/source hashes, bytecode/ABI and output hashes. ABI selectors come from the reviewed compiled ABI; do not substitute Python SHA3 for Ethereum Keccak.

Deployment script: test-contracts/script/DeployEXSepoliaTestNFT.s.sol:DeployEXSepoliaTestNFT. It reads only the public EX_TEST_ISSUER address and uses startBroadcast(issuer), requiring the existing approved signer to resolve that same account. It has no private-key variable, secret loader, new wallet or guessed RPC URL. Actual deployment remains with the original Operations owner after exact source/artifact/signing/gas bindings. Do not run this script merely because the source is present. The deployment receipt, actual contract address/runtime code hash, issuer/task/TEST_ONLY reads and Sepolia identity must be reconciled before admitting any mint.

## Agent admission and actual mint evidence

The original shared Wallet typed mint route must explicitly admit Sepolia using EX's separate original origin, tenant, wallets and signer identities. A Hoodi-only schema is not compatible. The server-owned TESTONLY inventory binds taskId, actor, chain, standard ERC721, actual contract runtime code hash, immutable issuer, source SHA-256 and selected sourceKind to this exact mint method with value zero and no target/recipient override. Planned mint has no invented transaction, block or token IDs. The authenticated source document must visibly state simulated, TESTONLY, no real value and no production evidence eligibility. Do not feed it into a production RWA source verifier or relax that verifier.

Agent signing and password/authenticator exemption apply only inside the existing specific grant and this task's authorized valueless test assets. Original nonce, balances, exact fee upper bound, buyer gas quote/confirmation/pre-freeze and unknown-result reconciliation remain mandatory. This contract does not implement those wallet checks. Mint authorization is not a fiat/token payment or an unlimited token approval.

Successful confirmation requires a status-one receipt on Sepolia from the actual admitted contract and original issuer-signed transaction. Decode both Transfer(address(0), issuer, tokenId) and TestReceiptMinted(taskId, sourceHash, tokenId, sourceKind, issuer, metadataURIHash) from that same transaction and emitter; require exact agreement. metadataURIHash is keccak256 of the exact tokenURI bytes, distinct from the source SHA-256. Read back ownerOf, sourceHashOf, sourceKindOf, mintedTokenForSource, tokenURI, issuer and TASK_ID at the confirmed block under the original finality policy. A mock event or local test is not a mint receipt.

If broadcast result is unknown, query the original signer/nonce/transaction and mintedTokenForSource first. Never blindly issue another mint. A duplicate-source revert is not proof of which transaction succeeded. Failed transactions consume actual gas and do not yield tokens. Actual deployment/mint gas, transaction/block/receipt hashes and token IDs remain null until observed. This initial package has no deployed address, runtime code hash or successful chain result.

## Current validation status

Twelve authored synthetic Foundry test functions cover chain/issuer/task constraints, the three source kinds, duplicate/invalid source refusal, exact event mapping, metadata preservation, token-scoped approval/transfer and blanket approval refusal. Tests, compiler, deployment, signer, provider, mint, UI and full-product acceptance are NOT_RUN. Source publication does not close the original full PRD or the seven integration gaps.
