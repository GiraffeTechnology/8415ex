// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";

/// Read subset of the fixed ERC-8415 IRegisterProjection ABI.
interface IEXRegisterProjection {
    function supportsInterface(bytes4 interfaceId) external view returns (bool);
    function registerId() external view returns (bytes32);
    function holderAsOf(uint256 tokenId, uint64 instant) external view returns (address);
}

/// Sepolia test candidate. Projection installation and real acceptance remain required.
/// Currency references identify original currency/network/unit declarations; they are
/// not balances, exchange rates, or permission to substitute a payment asset.
contract EXNFT0Remint is ERC721 {
    error InvalidBinding();
    error InvalidDeclaration();
    error NotIssuer();
    error NotHolderAndOwner();
    error ReentrantOperation();
    error OperationConflict();
    error RecipientChanged();

    struct Declaration {
        bytes32 billKey;
        bytes32 termsHash;
        bytes32 currencyDeclarationHash;
        bytes32[] allowedCurrencies;
    }

    struct Operation {
        bytes32 digest;
        uint256 newTokenId;
    }

    bytes4 private constant PROJECTION_INTERFACE_ID = 0x6309e170;
    address public immutable issuer;
    IEXRegisterProjection public immutable projection;
    bytes32 public immutable originalRegisterId;
    uint256 public nextTokenId = 1;
    mapping(uint256 => Declaration) private declarations;
    mapping(bytes32 => uint256) public activeTokenForBill;
    mapping(uint256 => uint256) public predecessorOf;
    mapping(uint256 => uint256) public successorOf;
    mapping(bytes32 => Operation) private operations;
    bool private entered;

    event NFT0Declared(uint256 indexed tokenId, bytes32 indexed billKey,
        bytes32 termsHash, bytes32 currencyDeclarationHash, bytes32[] allowedCurrencies);
    event NFT0Reminted(bytes32 indexed operationId, uint256 indexed oldTokenId,
        uint256 indexed newTokenId, address holder, bytes32 billKey);

    modifier atomicOperation() {
        if (entered) revert ReentrantOperation();
        entered = true;
        _;
        entered = false;
    }

    constructor(address issuer_, address projection_, bytes32 registerId_)
        ERC721("EX NFT0 Remint Test", "EX0TEST")
    {
        if (block.chainid != 11155111 || issuer_ == address(0)
            || projection_.code.length == 0 || registerId_ == bytes32(0)) {
            revert InvalidBinding();
        }
        IEXRegisterProjection original = IEXRegisterProjection(projection_);
        if (!original.supportsInterface(PROJECTION_INTERFACE_ID)
            || original.registerId() != registerId_) revert InvalidBinding();
        issuer = issuer_;
        projection = original;
        originalRegisterId = registerId_;
    }

    function mintNFT0(address recipient, Declaration calldata declared)
        external atomicOperation returns (uint256 tokenId)
    {
        if (msg.sender != issuer) revert NotIssuer();
        _validate(declared);
        if (recipient == address(0) || activeTokenForBill[declared.billKey] != 0) {
            revert InvalidDeclaration();
        }
        tokenId = nextTokenId++;
        declarations[tokenId] = declared;
        activeTokenForBill[declared.billKey] = tokenId;
        _safeMint(recipient, tokenId);
        if (_ownerOf(tokenId) != recipient) revert RecipientChanged();
        _emitDeclaration(tokenId);
    }

    function remintNFT0(bytes32 operationId, uint256 oldTokenId,
        Declaration calldata replacement)
        external atomicOperation returns (uint256 newTokenId)
    {
        if (operationId == bytes32(0)) revert InvalidDeclaration();
        bytes32 digest = keccak256(abi.encode(msg.sender, oldTokenId, replacement));
        Operation storage prior = operations[operationId];
        if (prior.newTokenId != 0) {
            if (prior.digest != digest) revert OperationConflict();
            return prior.newTokenId;
        }
        if (_ownerOf(oldTokenId) != msg.sender) revert NotHolderAndOwner();
        // No gap, finality, refund, cleanup, or separate approval predicate.
        // Ordinary inherited ERC721 transfers do not invoke this projection.
        if (block.timestamp > type(uint64).max
            || projection.holderAsOf(oldTokenId, uint64(block.timestamp)) != msg.sender) {
            revert NotHolderAndOwner();
        }
        _validate(replacement);
        bytes32 billKey = declarations[oldTokenId].billKey;
        if (replacement.billKey != billKey || activeTokenForBill[billKey] != oldTokenId) {
            revert InvalidDeclaration();
        }
        newTokenId = nextTokenId++;
        declarations[newTokenId] = replacement;
        predecessorOf[newTokenId] = oldTokenId;
        successorOf[oldTokenId] = newTokenId;
        activeTokenForBill[billKey] = newTokenId;
        operations[operationId] = Operation(digest, newTokenId);
        _burn(oldTokenId);
        _safeMint(msg.sender, newTokenId);
        if (_ownerOf(newTokenId) != msg.sender) revert RecipientChanged();
        _emitDeclaration(newTokenId);
        emit NFT0Reminted(operationId, oldTokenId, newTokenId, msg.sender, billKey);
    }

    /// Retained for burned tokens; there is deliberately no declaration setter.
    function declarationOf(uint256 tokenId) external view returns (Declaration memory) {
        if (declarations[tokenId].billKey == bytes32(0)) revert InvalidDeclaration();
        return declarations[tokenId];
    }

    /// UNKNOWN callers reconcile this result and receipts before any new action.
    function operationResult(bytes32 operationId) external view returns (Operation memory) {
        return operations[operationId];
    }

    function _validate(Declaration calldata declared) private pure {
        uint256 length = declared.allowedCurrencies.length;
        if (declared.billKey == bytes32(0) || declared.termsHash == bytes32(0)
            || declared.currencyDeclarationHash == bytes32(0) || length == 0) {
            revert InvalidDeclaration();
        }
        for (uint256 i; i < length; ++i) {
            if (declared.allowedCurrencies[i] == bytes32(0)) revert InvalidDeclaration();
            for (uint256 j; j < i; ++j) {
                if (declared.allowedCurrencies[j] == declared.allowedCurrencies[i]) {
                    revert InvalidDeclaration();
                }
            }
        }
    }

    function _emitDeclaration(uint256 tokenId) private {
        Declaration storage declared = declarations[tokenId];
        emit NFT0Declared(tokenId, declared.billKey, declared.termsHash,
            declared.currencyDeclarationHash, declared.allowedCurrencies);
    }
}
