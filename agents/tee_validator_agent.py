"""
TEE Validator Agent

Enhanced validator agent with TEE capabilities.
"""

import json
import os
from typing import Dict, Any

from .base_agent_genesis import GenesisBaseAgent
from .validator_proof_service import ValidatorProofService
from .registry_reader import VerifiedIdentityRegistryReader
from .a2a_verification_service import A2AVerificationService


class TEEValidatorAgent(GenesisBaseAgent):
    """TEE-enabled validator agent"""

    def __init__(self, agent_domain: str, wallet_address: str, wallet_manager=None):
        """Initialize TEE validator agent"""
        super().__init__(agent_domain, wallet_address, wallet_manager)

        # Initialize TEE components
        self.validator_proof_service = ValidatorProofService(
            dstack_endpoint=os.getenv('DSTACK_SIMULATOR_ENDPOINT')
        )
        self.registry_reader = None
        self.verification_service = None

        # Setup TEE components
        self._setup_tee_components()

    def _setup_tee_components(self):
        """Setup TEE validation components"""
        try:
            # Load VerifiedIdentityRegistry contract
            verified_registry_contract = self._load_verified_identity_registry()

            if verified_registry_contract:
                # Initialize registry reader
                self.registry_reader = VerifiedIdentityRegistryReader(
                    self.w3,
                    verified_registry_contract.address,
                    verified_registry_contract.abi
                )

                # Initialize verification service
                self.verification_service = A2AVerificationService(
                    self.registry_reader,
                    self.validator_proof_service
                )
                print("✅ TEE validation components initialized")
            else:
                print("⚠️  VerifiedIdentityRegistry not found, TEE validation disabled")

        except Exception as e:
            print(f"❌ Failed to setup TEE components: {e}")

    def _load_verified_identity_registry(self):
        """Load VerifiedIdentityRegistry contract"""
        try:
            deployment_files = {
                'local': 'deployment.json',
                'sepolia': 'deployments/sepolia.json',
                'base-sepolia': 'deployments/base-sepolia.json',
                'optimism-sepolia': 'deployments/optimism-sepolia.json'
            }

            deployment_file = deployment_files.get(self.network)
            if deployment_file:
                deployment_path = os.path.join(
                    os.path.dirname(__file__), '..', deployment_file)
                if os.path.exists(deployment_path):
                    with open(deployment_path, 'r') as f:
                        deployment_data = json.load(f)

                    verified_registry_address = deployment_data.get(
                        'contracts', {}).get('verified_identity_registry')
                    if verified_registry_address:
                        abi_path = os.path.join(
                            os.path.dirname(
                                __file__), '..', 'contracts', 'out',
                            'VerifiedIdentityRegistry.sol', 'VerifiedIdentityRegistry.json'
                        )
                        if os.path.exists(abi_path):
                            with open(abi_path, 'r') as f:
                                abi_data = json.load(f)

                            return self.w3.eth.contract(
                                address=verified_registry_address,
                                abi=abi_data['abi']
                            )
            return None
        except Exception:
            return None

    def generate_validator_proof(self) -> Dict[str, Any]:
        """Generate ValidatorProof for this validator"""
        return self.validator_proof_service.generate_validator_proof(self.address)

    def handle_agent_validation_request(self, request_data: Dict[str, Any]):
        """Handle A2A agent validation request"""
        if not self.verification_service:
            raise ValueError("TEE verification service not available")

        return self.verification_service.verify_agent(
            request_data["agent_address"],
            request_data["quote_data"]
        )

    def update_trustless_agent_status(self, agent_address: str, trusted: bool) -> str:
        """Update trustless agent status in VerifiedIdentityRegistry"""
        if not self.registry_reader:
            raise ValueError("Registry not available")

        agent_name = self._get_agent_name_from_domain()
        wallet = self.wallet_manager.wallets.get(agent_name)

        if not wallet:
            raise ValueError(f"Wallet not found for validator: {agent_name}")

        contract_call = self.registry_reader.contract.functions.updateTrustlessAgent(
            agent_address, trusted
        )

        transaction = contract_call.build_transaction({
            'from': self.address,
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'chainId': self.chain_id
        })

        signed_txn = wallet.sign_transaction(transaction)
        raw_transaction = signed_txn.raw_transaction if hasattr(
            signed_txn, 'raw_transaction') else signed_txn.rawTransaction
        tx_hash = self.w3.eth.send_raw_transaction(raw_transaction)

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise Exception("Transaction failed")

        return tx_hash.hex()

    def is_dstack_available(self) -> bool:
        """Check if dstack is available"""
        return self.validator_proof_service.is_dstack_available()

    def check_validator_status(self) -> Dict[str, Any]:
        """Check validator registration status"""
        status = {
            "registry_available": self.registry_reader is not None,
            "is_registered_validator": False,
            "validator_proof_available": False
        }

        if self.registry_reader:
            try:
                # Check if validator proof is available
                proof = self.generate_validator_proof()
                status["validator_proof_available"] = proof is not None
            except Exception:
                status["validator_proof_available"] = False

        return status
