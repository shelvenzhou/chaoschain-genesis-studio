// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./interfaces/IVerifiedIdentityRegistry.sol";
import "./interfaces/IIdentityRegistry.sol";

/**
 * @title VerifiedIdentityRegistry
 * @dev Implementation of the Verified Identity Registry for TEE-based agent verification
 * @notice This contract manages TEE Validator Agents and maintains a registry of verified agent identities
 * @author ChaosChain Labs
 */
contract VerifiedIdentityRegistry is IVerifiedIdentityRegistry, Ownable {
    // ============ Constants ============

    /// @dev Contract version for tracking implementation changes
    string public constant VERSION = "1.0.0";

    // ============ State Variables ============

    /// @dev Reference to the IdentityRegistry for agent validation
    IIdentityRegistry public immutable identityRegistry;

    /// @dev Validator proof data
    ValidatorProof public validatorProof;

    /// @dev Mapping of allowed aggregated MR measurements for running Validator
    mapping(bytes32 => bool) public validatorAllowedAggregatedMrs;

    /// @dev Mapping of allowed KMS device IDs
    mapping(bytes32 => bool) public validatorAllowedDeviceIds;

    /// @dev Mapping of allowed agent measurements
    mapping(bytes32 => bool) public allowedAgentComposeHashes;

    /// @dev Mapping of validated agents
    mapping(address => bool) public trustlessAgents;

    // ============ Modifiers ============

    modifier onlyValidator() {
        if (validatorProof.agentAddress.length == 0) revert EmptyData();
        address validatorAddress = _bytesToAddress(validatorProof.agentAddress);
        if (msg.sender != validatorAddress) revert OnlyValidator();
        _;
    }

    // ============ Constructor ============

    /**
     * @dev Constructor sets the identity registry reference
     * @param initialOwner Address of the initial contract owner
     * @param _identityRegistry Address of the IdentityRegistry contract
     */
    constructor(address initialOwner, address _identityRegistry) Ownable(initialOwner) {
        identityRegistry = IIdentityRegistry(_identityRegistry);
    }

    // ============ Owner Functions ============

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function setValidatorProof(ValidatorProof calldata _validatorProofData) external onlyOwner {
        if (_validatorProofData.agentAddress.length == 0) revert EmptyData();
        if (_validatorProofData.agentPubkey.length == 0) revert EmptyData();

        validatorProof = _validatorProofData;
        emit ValidatorProofSet(_validatorProofData.agentAddress, _validatorProofData.agentPubkey);
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function setValidatorAllowedAggregatedMr(bytes32 mrHash, bool allowed) external onlyOwner {
        validatorAllowedAggregatedMrs[mrHash] = allowed;
        emit ValidatorAllowedAggregatedMrSet(mrHash, allowed);
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function setValidatorAllowedDeviceId(bytes32 deviceId, bool allowed) external onlyOwner {
        validatorAllowedDeviceIds[deviceId] = allowed;
        emit ValidatorAllowedDeviceIdSet(deviceId, allowed);
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function setAllowedAgentComposeHash(bytes32 hash, bool allowed) external onlyOwner {
        allowedAgentComposeHashes[hash] = allowed;
        emit AllowedAgentComposeHashSet(hash, allowed);
    }

    // ============ Validator Functions ============

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function updateTrustlessAgent(address agentAddress, bool trusted) external onlyValidator {
        trustlessAgents[agentAddress] = trusted;
        emit TrustlessAgentUpdated(agentAddress, trusted);
    }

    // ============ Read Functions ============

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function getValidatorProof() external view returns (ValidatorProof memory) {
        return validatorProof;
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function isValidatorAllowedAggregatedMr(bytes32 mrHash) external view returns (bool) {
        return validatorAllowedAggregatedMrs[mrHash];
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function isValidatorAllowedDeviceId(bytes32 deviceId) external view returns (bool) {
        return validatorAllowedDeviceIds[deviceId];
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function isAllowedAgentComposeHash(bytes32 hash) external view returns (bool) {
        return allowedAgentComposeHashes[hash];
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function isTrustlessAgent(address agentAddress) external view returns (bool) {
        return trustlessAgents[agentAddress];
    }

    /**
     * @inheritdoc IVerifiedIdentityRegistry
     */
    function getValidatorAddress() external view returns (address) {
        if (validatorProof.agentAddress.length == 0) return address(0);
        return _bytesToAddress(validatorProof.agentAddress);
    }

    // ============ Internal Functions ============

    /**
     * @dev Convert bytes to address
     * @param data The bytes data to convert (must be 20 bytes)
     * @return addr The resulting address
     */
    function _bytesToAddress(bytes memory data) internal pure returns (address addr) {
        if (data.length != 20) return address(0);
        assembly {
            addr := mload(add(data, 20))
        }
    }
}