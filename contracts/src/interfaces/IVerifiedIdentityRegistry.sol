// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IVerifiedIdentityRegistry
 * @dev Interface for the Verified Identity Registry for TEE-based agent verification
 * @notice This contract manages TEE Validator Agents and maintains a registry of verified agent identities
 */
interface IVerifiedIdentityRegistry {

    // ============ Structs ============

    struct ValidatorProof {
        bytes agentAddress;      // Validator's public key
        bytes agentPubkey;       // A2A RSA public key
        bytes quote;             // TEE attestation report
        bytes eventlog;          // TEE event log
    }

    // ============ Events ============

    event ValidatorProofSet(bytes agentAddress, bytes agentPubkey);
    event ValidatorAllowedAggregatedMrSet(bytes32 indexed mrHash, bool allowed);
    event ValidatorAllowedDeviceIdSet(bytes32 indexed deviceId, bool allowed);
    event AllowedAgentComposeHashSet(bytes32 indexed hash, bool allowed);
    event TrustlessAgentUpdated(address indexed agentAddress, bool trusted);

    // ============ Errors ============

    error OnlyValidator();
    error EmptyData();
    error ArrayLengthMismatch();

    // ============ State Variables Access ============
    // Note: Public state variables automatically generate getter functions
    // validatorProof() - auto-generated
    // validatorAllowedAggregatedMrs(bytes32) - auto-generated
    // validatorAllowedDeviceIds(bytes32) - auto-generated
    // allowedAgentComposeHashes(bytes32) - auto-generated
    // trustlessAgents(uint256) - auto-generated

    // ============ Owner Functions ============

    function setValidatorProof(ValidatorProof calldata _validatorProof) external;
    function setValidatorAllowedAggregatedMr(bytes32 mrHash, bool allowed) external;
    function setValidatorAllowedDeviceId(bytes32 deviceId, bool allowed) external;
    function setAllowedAgentComposeHash(bytes32 hash, bool allowed) external;

    // ============ Validator Functions ============

    function updateTrustlessAgent(address agentAddress, bool trusted) external;

    // ============ Read Functions ============

    function getValidatorProof() external view returns (ValidatorProof memory);
    function isValidatorAllowedAggregatedMr(bytes32 mrHash) external view returns (bool);
    function isValidatorAllowedDeviceId(bytes32 deviceId) external view returns (bool);
    function isAllowedAgentComposeHash(bytes32 hash) external view returns (bool);
    function isTrustlessAgent(address agentAddress) external view returns (bool);
    function getValidatorAddress() external view returns (address);
}