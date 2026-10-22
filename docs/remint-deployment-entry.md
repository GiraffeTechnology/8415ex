# Original NFT0 remint deployment entry

DeployEXNFT0Remint is a source-only entry for the existing EXNFT0Remint Sepolia
test candidate. It reuses the existing DeployEXSepoliaTestNFT deployment
interface and public EX_TEST_ISSUER address. It adds no private-key environment
variable, signer import, endpoint, account, projection or replacement registry.

The original approved deployment owner must supply the actual existing
projection address and original register ID. The entry checks the original
constructor's Sepolia, nonzero issuer, projection code, fixed IRegisterProjection
interface and register identity before entering the existing broadcast boundary.
The constructor repeats its own checks. The script then checks the new
contract's issuer, original projection/register binding and initial next-token
counter. It does not mint, remint, transfer, freeze funds or choose bill terms.

These are existing constructor requirements, not new human approvals, custody
migration or full-product readiness conditions. Missing deployment parameters
must be recovered from the original verified configuration. Do not guess,
replace an original projection, select another chain or export a wallet key to
make this script runnable. Source publication grants no additional execution
authority and does not resume a refused operation.

Eight synthetic Solidity definitions exercise only the pre-broadcast input
validation through a harness; they do not call run or startBroadcast. They cover
the exact binding, wrong chain, zero issuer, absent code, zero/mismatched
register ID, unsupported interface and unavailable projection. Compiler/tests
have not been run by the author. The broadcast path and deployed-contract
readback have not been executed. Existing custody/signing, transaction outcome,
receipt/code/source identity, actual projection, Wallet integration and native
financial/chain acceptance remain separate original duties.

No actual projection address, register ID, signer configuration, transaction,
deployed address or live result is supplied or claimed by this stage.
