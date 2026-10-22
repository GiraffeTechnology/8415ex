# EXNFT0 remint ABI arguments

encode_remint_arguments encodes the arguments of the existing
[EXNFT0Remint.remintNFT0](../test-contracts/src/EXNFT0Remint.sol) signature:
`remintNFT0(bytes32,uint256,(bytes32,bytes32,bytes32,bytes32[]))`.
The outer tuple has three head words; its dynamic declaration begins at byte
96. The declaration has four head words, with its currency array at byte 128
relative to that declaration. The array preserves its original order and has a
uint256 count followed by bytes32 currency references. Layout follows the
[Solidity 0.8.24 ABI specification](https://docs.soliditylang.org/en/v0.8.24/abi-spec.html).

The function returns arguments only, without a four-byte selector, destination,
sender, chain, value or transaction. The original compatible Wallet/contract
encoder must use the original ABI and Ethereum Keccak selector. This module
does not substitute SHA3-256 or SHA-256, or invent a generic Wallet operation.
It encodes no deployment or transaction request.

Inputs are the already established nonzero EVM operation ID, uint256 old token
ID and exact original replacement bill key, terms hash, currency declaration
hash and unique nonzero currency references. The installed original semantic
mapping must supply these words. It does not hash UUIDs, EX history digests,
business documents or currency labels into convenient replacements. Encoding
shape is not evidence that the words describe the right original declaration.

The original contract retains possession and effective-holder equality, stable
bill identity, active-token uniqueness, atomic burn/mint, operation idempotency,
history links and receiver checks. This encoder neither checks nor adds
cleanup, refund, gap, finality or separate approval predicates. It does not
choose a contract, wallet, gas budget, authorization or nonce, and performs no
signing, RPC, broadcast, persistence or business mutation.

Eight Python definitions and one independent Solidity abi.encode vector are
authored, not executed by the author. Both use the same explicit 320-byte
two-currency vector. Additional Python definitions cover original ordering,
one/multiple currency counts, exact uint256 representation, invalid words,
duplicate references and detached inputs. Compiler and cross-language results,
original semantic mapping, compatible Wallet operation, installed contract and
live financial/chain acceptance remain open.
