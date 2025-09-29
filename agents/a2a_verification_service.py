"""
A2A Agent Verification Service

Simple TEE agent verification service.
"""

import json
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

from .validator_proof_service import ValidatorProofService
from .registry_reader import VerifiedIdentityRegistryReader


class VerificationStatus(Enum):
    """Verification status"""
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of agent validation"""
    status: VerificationStatus
    agent_address: str
    error_message: str = ""


class A2AVerificationService:
    """Simple A2A agent verification service"""

    def __init__(self, registry_reader: VerifiedIdentityRegistryReader,
                 validator_proof_service: ValidatorProofService):
        """Initialize the verification service"""
        self.registry_reader = registry_reader
        self.validator_proof_service = validator_proof_service

    def verify_agent(self, agent_address: str, quote_data: Dict[str, Any]) -> ValidationResult:
        """Verify agent using TEE quote"""
        try:
            # Parse quote
            quote_bytes = json.dumps(quote_data).encode()
            boot_info = self.validator_proof_service.verify_quote(quote_bytes)

            # Check allowlists
            if not self.registry_reader.is_allowed_agent_compose_hash(boot_info.compose_hash):
                return ValidationResult(
                    status=VerificationStatus.REJECTED,
                    agent_address=agent_address,
                    error_message="Compose hash not allowed"
                )

            if not self.registry_reader.is_validator_allowed_device_id(boot_info.device_id):
                return ValidationResult(
                    status=VerificationStatus.REJECTED,
                    agent_address=agent_address,
                    error_message="Device ID not allowed"
                )

            # TODO.shelven: enable this
            # if not self.registry_reader.is_validator_allowed_mr(boot_info.aggregated_mr):
            #     return ValidationResult(
            #         status=VerificationStatus.REJECTED,
            #         agent_address=agent_address,
            #         error_message="Measurement Register not allowed"
            #     )

            return ValidationResult(
                status=VerificationStatus.APPROVED,
                agent_address=agent_address
            )

        except Exception as e:
            return ValidationResult(
                status=VerificationStatus.ERROR,
                agent_address=agent_address,
                error_message=str(e)
            )
