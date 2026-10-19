// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {EXSepoliaTestNFT} from "../src/EXSepoliaTestNFT.sol";

interface VmEXDeploy {
    function envAddress(string calldata name) external returns (address);
    function startBroadcast(address signer) external;
    function stopBroadcast() external;
}

/// @notice Deployment input only; run by the existing approved deployment owner.
/// @dev EX_TEST_ISSUER is a public address. No private-key environment variable.
contract DeployEXSepoliaTestNFT {
    VmEXDeploy private constant vm =
        VmEXDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    function run() external returns (EXSepoliaTestNFT nft) {
        require(block.chainid == 11155111, "EX Sepolia only");
        address issuer = vm.envAddress("EX_TEST_ISSUER");
        require(issuer != address(0), "explicit approved issuer required");
        // Existing signer control must resolve this same approved address.
        // No caller calldata target, delegatecall, issuer setter or key import.
        vm.startBroadcast(issuer);
        nft = new EXSepoliaTestNFT(issuer);
        vm.stopBroadcast();
        require(nft.issuer() == issuer && nft.TEST_ONLY(), "deployment binding");
    }
}
