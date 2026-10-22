// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {DeployEXNFT0Remint} from "../script/DeployEXNFT0Remint.s.sol";

interface RemintDeployVm {
    function chainId(uint256) external;
}

// Synthetic preflight only. These tests never call run/startBroadcast.
contract RemintDeployProjectionFixture {
    bytes32 public registerId = bytes32(uint256(1));
    bool public supported = true;
    bool public unavailable;

    function configure(bool supported_, bool unavailable_) external {
        supported = supported_;
        unavailable = unavailable_;
    }

    function supportsInterface(bytes4 id) external view returns (bool) {
        require(!unavailable, "synthetic projection unavailable");
        return supported && id == 0x6309e170;
    }
}

contract RemintDeployInputHarness is DeployEXNFT0Remint {
    function check(address issuer, address projection, bytes32 registerId)
        external view returns (bool)
    {
        _checkOriginalInputs(issuer, projection, registerId);
        return true;
    }
}

contract DeployEXNFT0RemintInputTest {
    RemintDeployVm private constant vm =
        RemintDeployVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    RemintDeployInputHarness private harness;
    RemintDeployProjectionFixture private projection;
    address private constant SYNTHETIC_ISSUER = address(0xA11CE);

    function setUp() public {
        vm.chainId(11155111);
        harness = new RemintDeployInputHarness();
        projection = new RemintDeployProjectionFixture();
    }

    function rejected(address issuer, address original, bytes32 registerId)
        private view returns (bool)
    {
        (bool ok,) = address(harness).staticcall(
            abi.encodeCall(RemintDeployInputHarness.check, (issuer, original, registerId)));
        return !ok;
    }

    function testExactOriginalBindingAcceptedBeforeAnyBroadcast() public view {
        require(harness.check(SYNTHETIC_ISSUER, address(projection), projection.registerId()));
    }

    function testDifferentChainRejected() public {
        vm.chainId(560048);
        require(rejected(SYNTHETIC_ISSUER, address(projection), projection.registerId()));
    }

    function testZeroIssuerRejected() public view {
        require(rejected(address(0), address(projection), projection.registerId()));
    }

    function testMissingProjectionCodeRejected() public view {
        require(rejected(SYNTHETIC_ISSUER, address(0), projection.registerId()));
        require(rejected(SYNTHETIC_ISSUER, address(0x1234), projection.registerId()));
    }

    function testZeroOriginalRegisterIdRejected() public view {
        require(rejected(SYNTHETIC_ISSUER, address(projection), bytes32(0)));
    }

    function testUnsupportedOriginalInterfaceRejected() public {
        projection.configure(false, false);
        require(rejected(SYNTHETIC_ISSUER, address(projection), projection.registerId()));
    }

    function testDifferentOriginalRegisterIdentityRejected() public view {
        require(rejected(SYNTHETIC_ISSUER, address(projection), bytes32(uint256(2))));
    }

    function testUnavailableProjectionCannotFallThroughToBroadcast() public {
        projection.configure(true, true);
        require(rejected(SYNTHETIC_ISSUER, address(projection), projection.registerId()));
    }
}
