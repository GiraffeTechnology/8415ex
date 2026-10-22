// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {EXNFT0Remint, IEXRegisterProjection} from "../src/EXNFT0Remint.sol";
import {VmEXDeploy} from "./DeployEXSepoliaTestNFT.s.sol";

/// @notice Source-only entry for the existing authorized Sepolia deployment owner.
/// @dev Reuses public EX_TEST_ISSUER; no private-key or endpoint input is added.
contract DeployEXNFT0Remint {
    VmEXDeploy private constant vm =
        VmEXDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    function _checkOriginalInputs(address issuer, address originalProjection, bytes32 originalRegisterId)
        internal view
    {
        require(block.chainid == 11155111, "EX Sepolia only");
        require(issuer != address(0), "explicit approved issuer required");
        require(originalProjection.code.length != 0 && originalRegisterId != bytes32(0),
            "original projection binding required");
        IEXRegisterProjection original = IEXRegisterProjection(originalProjection);
        require(original.supportsInterface(0x6309e170)
            && original.registerId() == originalRegisterId, "original register binding differs");
    }

    function run(address originalProjection, bytes32 originalRegisterId)
        external returns (EXNFT0Remint nft)
    {
        address issuer = vm.envAddress("EX_TEST_ISSUER");
        _checkOriginalInputs(issuer, originalProjection, originalRegisterId);
        // The existing signer must resolve the same approved issuer. No key
        // import, replacement projection, registrar or fallback actor is created.
        vm.startBroadcast(issuer);
        nft = new EXNFT0Remint(issuer, originalProjection, originalRegisterId);
        vm.stopBroadcast();
        require(nft.issuer() == issuer && address(nft.projection()) == originalProjection
            && nft.originalRegisterId() == originalRegisterId && nft.nextTokenId() == 1,
            "deployed remint binding differs");
    }
}
