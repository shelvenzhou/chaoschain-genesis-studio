"""
VerifiedIdentityRegistry Reader

Simple service for reading VerifiedIdentityRegistry contract state.
"""

from typing import Optional
from web3 import Web3
from web3.contract import Contract


class VerifiedIdentityRegistryReader:
    """Simple service for reading VerifiedIdentityRegistry contract state"""

    def __init__(self, web3: Web3, contract_address: str, contract_abi: list):
        """Initialize the registry reader"""
        self.w3 = web3
        self.contract = web3.eth.contract(
            address=contract_address, abi=contract_abi)

    def get_validator_proof(self):
        """Get the current validator proof from contract"""
        try:
            proof = self.contract.functions.getValidatorProof().call()
            if not proof[0]:  # agentAddress is empty
                return None
            return {
                "agent_address": proof[0],
                "agent_pubkey": proof[1],
                "quote": proof[2],
                "eventlog": proof[3]
            }
        except Exception:
            return None

    def is_validator_allowed_mr(self, mr_hash: bytes) -> bool:
        """Check if MR hash is allowed for validator"""
        try:
            return self.contract.functions.isValidatorAllowedAggregatedMr(mr_hash).call()
        except Exception:
            return False

    def is_validator_allowed_device_id(self, device_id: bytes) -> bool:
        """Check if device ID is allowed for validator"""
        try:
            return self.contract.functions.isValidatorAllowedDeviceId(device_id).call()
        except Exception:
            return False

    def is_allowed_agent_compose_hash(self, compose_hash: bytes) -> bool:
        """Check if compose hash is allowed for agents"""
        try:
            return self.contract.functions.isAllowedAgentComposeHash(compose_hash).call()
        except Exception:
            return False

    def is_trustless_agent(self, agent_address: str) -> bool:
        """Check if agent is marked as trustless"""
        try:
            return self.contract.functions.isTrustlessAgent(agent_address).call()
        except Exception:
            return False

    def get_validator_address(self) -> Optional[str]:
        """Get the current validator address"""
        try:
            return self.contract.functions.getValidatorAddress().call()
        except Exception:
            return None
