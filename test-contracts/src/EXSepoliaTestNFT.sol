// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

/// @notice Valueless simulated warehouse-receipt NFTs on Sepolia only.
/// @dev Not a production warehouse receipt, Oracle, escrow or title registry.
contract EXSepoliaTestNFT is ERC721 {
    using Strings for uint256;

    uint256 public constant TEST_CHAIN_ID = 11155111;
    bytes32 public constant TASK_ID = keccak256("8415EX");
    bool public constant TEST_ONLY = true;
    address public immutable issuer;
    uint256 private nextTokenId = 1;
    bool private minting;

    mapping(bytes32 => uint256) public mintedTokenForSource;
    mapping(uint256 => bytes32) public sourceHashOf;
    mapping(uint256 => uint8) public sourceKindOf;

    error WrongTestChain();
    error InvalidIssuer();
    error IssuerOnly();
    error InvalidSource();
    error SourceAlreadyMinted();
    error MintInProgress();
    error MintRecipientChanged();
    error UnlimitedApprovalDisabled();

    /// @dev metadataURIHash is keccak256(bytes(tokenURI(tokenId))), not source SHA-256.
    event TestReceiptMinted(
        bytes32 indexed taskId,
        bytes32 indexed sourceHash,
        uint256 indexed tokenId,
        uint8 sourceKind,
        address issuer,
        bytes32 metadataURIHash
    );

    constructor(address issuer_) ERC721("EX TESTONLY Simulated Receipt", "EXTEST") {
        if (block.chainid != TEST_CHAIN_ID) revert WrongTestChain();
        if (issuer_ == address(0)) revert InvalidIssuer();
        issuer = issuer_;
    }

    /// @param sourceHash SHA-256 of the exact TESTONLY simulation document bytes.
    /// @param sourceKind 1=direct, 2=electronic, 3=intermediary simulated role.
    /// @dev Fixed recipient is this deployment's immutable approved issuer.
    function mintSimulatedReceipt(bytes32 sourceHash, uint8 sourceKind)
        external returns (uint256 tokenId)
    {
        if (block.chainid != TEST_CHAIN_ID) revert WrongTestChain();
        if (msg.sender != issuer) revert IssuerOnly();
        if (minting) revert MintInProgress();
        if (sourceHash == bytes32(0) || sourceKind < 1 || sourceKind > 3) revert InvalidSource();
        if (mintedTokenForSource[sourceHash] != 0) revert SourceAlreadyMinted();
        minting = true;
        tokenId = nextTokenId++;
        mintedTokenForSource[sourceHash] = tokenId;
        sourceHashOf[tokenId] = sourceHash;
        sourceKindOf[tokenId] = sourceKind;
        _safeMint(issuer, tokenId);
        if (ownerOf(tokenId) != issuer) revert MintRecipientChanged();
        emit TestReceiptMinted(TASK_ID, sourceHash, tokenId, sourceKind, issuer,
            keccak256(bytes(tokenURI(tokenId))));
        minting = false;
    }

    /// @notice Per-token approve remains available; blanket operator approval does not.
    function setApprovalForAll(address, bool) public pure override {
        revert UnlimitedApprovalDisabled();
    }

    /// @notice Metadata is deterministic, on-chain and cannot be set by the caller.
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        string memory path = sourceKindOf[tokenId] == 1 ? "REG_DIRECT"
            : sourceKindOf[tokenId] == 2 ? "REG_ELECTRONIC" : "REG_INTERMEDIARY";
        bytes memory body = abi.encodePacked(
            '{"name":"TESTONLY EX Simulated Receipt #', tokenId.toString(),
            '","description":"No real-world value. Simulated document only. No real warehouse, legal title, physical pickup or burn claim.",',
            '"testOnly":true,"taskId":"8415EX","chainId":11155111,',
            '"standard":"ERC721","wholeReceiptUnits":1,"productionEvidence":false,',
            '"sourceSHA256":"', Strings.toHexString(uint256(sourceHashOf[tokenId]), 32),
            '","registrationPath":"', path, '"}'
        );
        return string.concat("data:application/json;base64,", Base64.encode(body));
    }
}
