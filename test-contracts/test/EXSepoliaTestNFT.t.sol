// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {EXSepoliaTestNFT} from "../src/EXSepoliaTestNFT.sol";

interface VmEXTest {
    struct Log { bytes32[] topics; bytes data; address emitter; }
    function chainId(uint256) external;
    function prank(address) external;
    function expectRevert(bytes4) external;
    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
}

/// @dev Authored synthetic tests only. No real signer or network is referenced.
contract EXSepoliaTestNFTTest {
    VmEXTest private constant vm =
        VmEXTest(address(uint160(uint256(keccak256("hevm cheat code")))));
    address private constant ISSUER = address(0xA11CE);
    address private constant OTHER = address(0xB0B);
    EXSepoliaTestNFT private nft;

    function setUp() public {
        vm.chainId(11155111);
        nft = new EXSepoliaTestNFT(ISSUER);
    }

    function mint(bytes32 source, uint8 kind) private returns (uint256) {
        vm.prank(ISSUER);
        return nft.mintSimulatedReceipt(source, kind);
    }

    function testIssuerTaskAndChainAreFixed() public view {
        require(nft.issuer() == ISSUER, "issuer");
        require(nft.TASK_ID() == keccak256("8415EX"), "task");
        require(nft.TEST_ONLY() && nft.TEST_CHAIN_ID() == 11155111, "test domain");
    }

    function testWrongDeploymentChainRefused() public {
        vm.chainId(560048);
        vm.expectRevert(EXSepoliaTestNFT.WrongTestChain.selector);
        new EXSepoliaTestNFT(ISSUER);
    }

    function testZeroIssuerRefused() public {
        vm.expectRevert(EXSepoliaTestNFT.InvalidIssuer.selector);
        new EXSepoliaTestNFT(address(0));
    }

    function testUnauthorizedMintRefused() public {
        vm.prank(OTHER);
        vm.expectRevert(EXSepoliaTestNFT.IssuerOnly.selector);
        nft.mintSimulatedReceipt(bytes32(uint256(1)), 1);
    }

    function testMintOnChangedChainRefused() public {
        vm.chainId(1);
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.WrongTestChain.selector);
        nft.mintSimulatedReceipt(bytes32(uint256(1)), 1);
    }

    function testSourceAndAllThreeKindsBound() public {
        for (uint8 kind = 1; kind <= 3; kind++) {
            bytes32 source = sha256(abi.encode("SYNTHETIC-TESTONLY", kind));
            uint256 id = mint(source, kind);
            require(nft.ownerOf(id) == ISSUER, "recipient");
            require(nft.sourceHashOf(id) == source, "source");
            require(nft.sourceKindOf(id) == kind, "kind");
            require(nft.mintedTokenForSource(source) == id, "reverse mapping");
            require(bytes(nft.tokenURI(id)).length > 29, "metadata");
        }
    }

    function testDuplicateSourceAcrossKindsRefused() public {
        bytes32 source = sha256("SIMULATED TESTONLY");
        mint(source, 1);
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.SourceAlreadyMinted.selector);
        nft.mintSimulatedReceipt(source, 2);
    }

    function testInvalidSourcesRefused() public {
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.InvalidSource.selector);
        nft.mintSimulatedReceipt(bytes32(0), 1);
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.InvalidSource.selector);
        nft.mintSimulatedReceipt(bytes32(uint256(1)), 0);
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.InvalidSource.selector);
        nft.mintSimulatedReceipt(bytes32(uint256(1)), 4);
    }

    function testTransferAndDedicatedEventBindActualReturnedToken() public {
        vm.recordLogs();
        bytes32 source = sha256("SIMULATED LOG FIXTURE");
        uint256 id = mint(source, 3);
        VmEXTest.Log[] memory logs = vm.getRecordedLogs();
        require(logs.length == 2, "exact mint events");
        require(logs[0].emitter == address(nft) && logs[1].emitter == address(nft), "emitter");
        require(logs[0].topics[0] == keccak256("Transfer(address,address,uint256)"), "transfer event");
        require(logs[0].topics[1] == bytes32(0), "mint from zero");
        require(logs[0].topics[2] == bytes32(uint256(uint160(ISSUER))), "mint to issuer");
        require(uint256(logs[0].topics[3]) == id, "actual token");
        require(logs[1].topics[0] ==
            keccak256("TestReceiptMinted(bytes32,bytes32,uint256,uint8,address,bytes32)"), "dedicated event");
        require(logs[1].topics[1] == nft.TASK_ID() && logs[1].topics[2] == source, "task source");
        require(uint256(logs[1].topics[3]) == id, "same actual token");
        (uint8 kind, address issuer, bytes32 uriHash) =
            abi.decode(logs[1].data, (uint8, address, bytes32));
        require(kind == 3 && issuer == ISSUER, "event constraints");
        require(uriHash == keccak256(bytes(nft.tokenURI(id))), "metadata commitment");
    }

    function testPerTokenApprovalAndTransferPreserveMetadata() public {
        uint256 id = mint(sha256("SIMULATED TRANSFER FIXTURE"), 1);
        bytes32 uriHash = keccak256(bytes(nft.tokenURI(id)));
        vm.prank(ISSUER);
        nft.approve(OTHER, id);
        vm.prank(OTHER);
        nft.transferFrom(ISSUER, OTHER, id);
        require(nft.ownerOf(id) == OTHER, "transfer");
        require(nft.getApproved(id) == address(0), "approval cleared");
        require(keccak256(bytes(nft.tokenURI(id))) == uriHash, "immutable metadata");
        require(nft.issuer() == ISSUER, "issuer unchanged");
    }

    function testUnlimitedApprovalRefused() public {
        vm.prank(ISSUER);
        vm.expectRevert(EXSepoliaTestNFT.UnlimitedApprovalDisabled.selector);
        nft.setApprovalForAll(OTHER, true);
    }

    function testNoTokenURIForUnmintedId() public {
        (bool ok,) = address(nft).staticcall(abi.encodeWithSignature("tokenURI(uint256)", 999));
        require(!ok, "unminted metadata refused");
    }
}
