// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {EXNFT0Remint} from "../src/EXNFT0Remint.sol";
import {IERC721Receiver} from "@openzeppelin/contracts/token/ERC721/IERC721Receiver.sol";

interface RemintVm {
    function chainId(uint256) external;
    function prank(address) external;
    function expectRevert(bytes4) external;
}

// Synthetic projection is confined to authored tests, never an installed Oracle.
contract RemintProjectionFixture {
    bytes32 public constant registerId = keccak256("synthetic-register");
    address public holder;
    bool public unavailable;
    function supportsInterface(bytes4 id) external pure returns (bool) {
        return id == 0x6309e170;
    }
    function setHolder(address value) external { holder = value; }
    function setUnavailable() external { unavailable = true; }
    function holderAsOf(uint256, uint64) external view returns (address) {
        require(!unavailable, "synthetic projection unavailable");
        return holder;
    }
}

contract RemintReceiverFixture is IERC721Receiver {
    error ReceiverRejected();
    EXNFT0Remint private immutable nft;
    bool private rejecting;
    bool private reentering;
    address private transferRecipient;
    bool public reentryRejected;

    constructor(EXNFT0Remint original) { nft = original; }

    function configure(bool reject_, bool reenter_) external {
        rejecting = reject_;
        reentering = reenter_;
    }

    function transferDuringReceipt(address recipient) external {
        transferRecipient = recipient;
    }

    function replace(bytes32 operation, uint256 oldId, EXNFT0Remint.Declaration calldata next)
        external returns (uint256)
    {
        return nft.remintNFT0(operation, oldId, next);
    }

    function onERC721Received(address, address, uint256 tokenId, bytes calldata)
        external returns (bytes4)
    {
        require(msg.sender == address(nft));
        if (rejecting) revert ReceiverRejected();
        if (transferRecipient != address(0)) {
            nft.transferFrom(address(this), transferRecipient, tokenId);
        }
        if (reentering) {
            EXNFT0Remint.Declaration memory same = nft.declarationOf(tokenId);
            try nft.remintNFT0(keccak256("nested-operation"), tokenId, same) {
                revert("nested remint unexpectedly succeeded");
            } catch (bytes memory reason) {
                reentryRejected = reason.length == 4
                    && keccak256(reason) == keccak256(abi.encodeWithSelector(EXNFT0Remint.ReentrantOperation.selector));
                require(reentryRejected);
            }
        }
        return IERC721Receiver.onERC721Received.selector;
    }
}

abstract contract EXNFT0RemintTestBase {
    RemintVm internal constant vm = RemintVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address internal constant ALICE = address(0xA11CE);
    address internal constant BOB = address(0xB0B);
    EXNFT0Remint internal nft;
    RemintProjectionFixture internal projection;

    function setUp() public {
        vm.chainId(11155111);
        projection = new RemintProjectionFixture();
        nft = new EXNFT0Remint(address(this), address(projection), projection.registerId());
        projection.setHolder(ALICE);
        nft.mintNFT0(ALICE, declaration(1));
    }

    function declaration(uint256 version) internal pure returns (EXNFT0Remint.Declaration memory value) {
        bytes32[] memory currencies = new bytes32[](2);
        currencies[0] = keccak256("synthetic-ETH-reference");
        currencies[1] = keccak256(abi.encode("synthetic-token-reference", version));
        value = EXNFT0Remint.Declaration(keccak256("synthetic-bill"),
            keccak256(abi.encode("terms", version)),
            keccak256(abi.encode("currency-declaration", version)), currencies);
    }

    function receiverBill() internal returns (RemintReceiverFixture receiver, uint256 oldId) {
        receiver = new RemintReceiverFixture(nft);
        EXNFT0Remint.Declaration memory initial = declaration(1);
        initial.billKey = keccak256("receiver-bill");
        oldId = nft.mintNFT0(address(receiver), initial);
        projection.setHolder(address(receiver));
    }

}

contract EXNFT0RemintCoreTest is EXNFT0RemintTestBase {
    function testAtomicRemintRetainsHistoryAndBill() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        vm.prank(ALICE);
        uint256 newer = nft.remintNFT0(keccak256("operation"), 1, replacement);
        require(newer == 2 && nft.ownerOf(2) == ALICE);
        require(nft.predecessorOf(2) == 1 && nft.successorOf(1) == 2);
        require(nft.activeTokenForBill(replacement.billKey) == 2);
        EXNFT0Remint.Declaration memory oldTerms = nft.declarationOf(1);
        require(oldTerms.termsHash == declaration(1).termsHash);
        require(nft.declarationOf(2).termsHash == replacement.termsHash);
        (bool oldStillOwned,) = address(nft).staticcall(abi.encodeWithSignature("ownerOf(uint256)", 1));
        require(!oldStillOwned);
    }

    function testOrdinaryTransferDoesNotConsultHolderProjection() public {
        projection.setUnavailable();
        vm.prank(ALICE);
        nft.transferFrom(ALICE, BOB, 1);
        require(nft.ownerOf(1) == BOB);
    }

    function testUnequalHolderRefusesRemint() public {
        projection.setHolder(BOB);
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        vm.expectRevert(EXNFT0Remint.NotHolderAndOwner.selector);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("unequal"), 1, replacement);
    }

    function testIssuerCannotRemintAnothersNFT() public {
        vm.expectRevert(EXNFT0Remint.NotHolderAndOwner.selector);
        nft.remintNFT0(keccak256("issuer"), 1, declaration(2));
    }

    function testExactOperationIsIdempotent() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        bytes32 operation = keccak256("same-operation");
        vm.prank(ALICE);
        nft.remintNFT0(operation, 1, replacement);
        vm.prank(ALICE);
        require(nft.remintNFT0(operation, 1, replacement) == 2);
        require(nft.nextTokenId() == 3);
        replacement.termsHash = keccak256("conflicting-terms");
        vm.expectRevert(EXNFT0Remint.OperationConflict.selector);
        vm.prank(ALICE);
        nft.remintNFT0(operation, 1, replacement);
    }

    function testDuplicateCurrencyRejectedBeforeBurn() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.allowedCurrencies[1] = replacement.allowedCurrencies[0];
        vm.expectRevert(EXNFT0Remint.InvalidDeclaration.selector);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("duplicate"), 1, replacement);
        require(nft.ownerOf(1) == ALICE && nft.successorOf(1) == 0);
    }

    function testAnotherOperationCannotConsumeBurnedToken() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("first-remint"), 1, replacement);
        vm.expectRevert(EXNFT0Remint.NotHolderAndOwner.selector);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("second-remint"), 1, replacement);
        require(nft.nextTokenId() == 3);
    }

    function testRemintCannotReplaceStableBillIdentity() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.billKey = keccak256("different-bill");
        vm.expectRevert(EXNFT0Remint.InvalidDeclaration.selector);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("wrong-bill"), 1, replacement);
        require(nft.ownerOf(1) == ALICE && nft.nextTokenId() == 2);
        require(nft.activeTokenForBill(declaration(1).billKey) == 1);
    }

    function testEmptyReplacementCurrenciesRejectBeforeBurn() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.allowedCurrencies = new bytes32[](0);
        vm.expectRevert(EXNFT0Remint.InvalidDeclaration.selector);
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("empty-currencies"), 1, replacement);
        require(nft.ownerOf(1) == ALICE && nft.nextTokenId() == 2);
    }

    function testReplacementMayDeclareSingleCurrencyAndRetainOldSet() public {
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.allowedCurrencies = new bytes32[](1);
        replacement.allowedCurrencies[0] = keccak256("new-single-currency-reference");
        vm.prank(ALICE);
        nft.remintNFT0(keccak256("single-currency"), 1, replacement);
        EXNFT0Remint.Declaration memory oldTerms = nft.declarationOf(1);
        EXNFT0Remint.Declaration memory newTerms = nft.declarationOf(2);
        require(oldTerms.allowedCurrencies.length == 2);
        require(newTerms.allowedCurrencies.length == 1);
        require(newTerms.allowedCurrencies[0] == replacement.allowedCurrencies[0]);
        require(oldTerms.allowedCurrencies[0] == declaration(1).allowedCurrencies[0]);
    }

}

contract EXNFT0RemintReceiverTest is EXNFT0RemintTestBase {
    function testReceiverRejectionRollsBackBurnLinksAndOperation() public {
        (RemintReceiverFixture receiver, uint256 oldId) = receiverBill();
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.billKey = keccak256("receiver-bill");
        bytes32 operation = keccak256("rejected-remint");
        uint256 nextBefore = nft.nextTokenId();
        receiver.configure(true, false);
        vm.expectRevert(RemintReceiverFixture.ReceiverRejected.selector);
        receiver.replace(operation, oldId, replacement);
        require(nft.ownerOf(oldId) == address(receiver));
        require(nft.activeTokenForBill(replacement.billKey) == oldId);
        require(nft.successorOf(oldId) == 0 && nft.predecessorOf(nextBefore) == 0);
        require(nft.operationResult(operation).newTokenId == 0);
        require(nft.nextTokenId() == nextBefore);
        require(nft.declarationOf(oldId).termsHash == declaration(1).termsHash);
    }

    function testReceiverReentryCannotMintTwice() public {
        (RemintReceiverFixture receiver, uint256 oldId) = receiverBill();
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.billKey = keccak256("receiver-bill");
        uint256 nextBefore = nft.nextTokenId();
        receiver.configure(false, true);
        uint256 newId = receiver.replace(keccak256("outer-remint"), oldId, replacement);
        require(receiver.reentryRejected() && newId == nextBefore);
        require(nft.ownerOf(newId) == address(receiver));
        require(nft.nextTokenId() == nextBefore + 1);
        require(nft.operationResult(keccak256("nested-operation")).newTokenId == 0);
    }

    function testReceiverTransferDuringRemintRevertsWholeOperation() public {
        (RemintReceiverFixture receiver, uint256 oldId) = receiverBill();
        EXNFT0Remint.Declaration memory replacement = declaration(2);
        replacement.billKey = keccak256("receiver-bill");
        bytes32 operation = keccak256("receipt-transfer");
        uint256 nextBefore = nft.nextTokenId();
        receiver.transferDuringReceipt(BOB);
        vm.expectRevert(EXNFT0Remint.RecipientChanged.selector);
        receiver.replace(operation, oldId, replacement);
        require(nft.ownerOf(oldId) == address(receiver));
        require(nft.activeTokenForBill(replacement.billKey) == oldId);
        require(nft.successorOf(oldId) == 0 && nft.predecessorOf(nextBefore) == 0);
        require(nft.operationResult(operation).newTokenId == 0);
        require(nft.nextTokenId() == nextBefore);
    }
}
