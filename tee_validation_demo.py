#!/usr/bin/env python3
"""
ChaosChain TEE Validation Demo

A production-ready demonstration system for TEE-based agent validation with
multi-chain support and separated deployment steps for customer showcases.

Usage:
    # Step 1: Deploy contracts to a network
    python tee_validation_demo.py deploy --network base-sepolia

    # Step 2: Setup agents and generate TEE proofs
    python tee_validation_demo.py setup-agents --network base-sepolia

    # Step 3: Run validation flow
    python tee_validation_demo.py validate --network base-sepolia

    # All-in-one (for quick testing)
    python tee_validation_demo.py run-all --network local

Requirements:
- dstack simulator running with DSTACK_SIMULATOR_ENDPOINT set
- Foundry installed (anvil, forge, cast)
- Python dependencies from requirements.txt
- Network-specific RPC URLs in .env file
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import signal
import time
from pathlib import Path
from typing import Dict, Any, Optional
from web3 import Web3
from eth_account import Account

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from agents.tee_client_agent import TEEClientAgent
from agents.tee_validator_agent import TEEValidatorAgent


# Network configuration
NETWORKS = {
    "local": {
        "name": "Anvil Local Testnet",
        "rpc_url": "http://127.0.0.1:8545",
        "chain_id": 31337,
        "gas_price": 1000000000,  # 1 gwei
        "type": "local"
    },
    "base-sepolia": {
        "name": "Base Sepolia Testnet",
        "rpc_url": os.getenv("BASE_SEPOLIA_RPC_URL", ""),
        "chain_id": 84532,
        "gas_price": None,  # Use network's suggested gas price
        "type": "testnet"
    },
    "sepolia": {
        "name": "Ethereum Sepolia",
        "rpc_url": os.getenv("SEPOLIA_RPC_URL", ""),
        "chain_id": 11155111,
        "gas_price": None,
        "type": "testnet"
    },
    "optimism-sepolia": {
        "name": "Optimism Sepolia",
        "rpc_url": os.getenv("OPTIMISM_SEPOLIA_RPC_URL", ""),
        "chain_id": 11155420,
        "gas_price": None,
        "type": "testnet"
    }
}


class TEEValidationDemo:
    """TEE Validation Demo System with Multi-Chain Support"""

    def __init__(self, network: str = "local"):
        """Initialize the demo system"""
        self.network_name = network
        self.network_config = NETWORKS.get(network)

        if not self.network_config:
            raise ValueError(f"Unknown network: {network}. Available: {list(NETWORKS.keys())}")

        self.anvil_process = None
        self.w3 = None
        self.validator_agent = None
        self.client_agent = None
        self.base_dir = Path(__file__).parent
        self.contracts_dir = self.base_dir / "contracts"
        self.deployments_dir = self.base_dir / "deployments"
        self.deployments_dir.mkdir(exist_ok=True)

        print(f"🌐 Network: {self.network_config['name']} (Chain ID: {self.network_config['chain_id']})")

    def get_deployment_path(self) -> Path:
        """Get deployment file path for current network"""
        return self.deployments_dir / f"{self.network_name}.json"

    def load_deployment(self) -> Optional[Dict[str, Any]]:
        """Load existing deployment data"""
        deployment_path = self.get_deployment_path()
        if not deployment_path.exists():
            return None

        with open(deployment_path, 'r') as f:
            return json.load(f)

    def save_deployment(self, data: Dict[str, Any]):
        """Save deployment data"""
        deployment_path = self.get_deployment_path()
        with open(deployment_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Deployment saved: {deployment_path}")

    async def connect_to_network(self):
        """Connect to the configured network"""
        rpc_url = self.network_config["rpc_url"]

        if self.network_config["type"] == "local":
            # For local network, start Anvil if not running
            await self.start_anvil_testnet()
        else:
            if not rpc_url:
                raise ValueError(f"RPC URL not configured for {self.network_name}. Set in .env file.")

            print(f"🔗 Connecting to {self.network_config['name']}...")
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))

            if not self.w3.is_connected():
                raise RuntimeError(f"Failed to connect to {rpc_url}")

            actual_chain_id = self.w3.eth.chain_id
            if actual_chain_id != self.network_config["chain_id"]:
                raise RuntimeError(
                    f"Chain ID mismatch! Expected {self.network_config['chain_id']}, got {actual_chain_id}"
                )

            print(f"✅ Connected to {self.network_config['name']} (Chain ID: {actual_chain_id})")

    async def start_anvil_testnet(self):
        """Start Anvil local testnet (only for local network)"""
        print("🔧 Starting Anvil local testnet...")

        # Kill any existing anvil processes
        try:
            subprocess.run(["pkill", "-f", "anvil"], check=False)
        except:
            pass

        # Start anvil with specific configuration
        anvil_cmd = [
            "anvil",
            "--port", "8545",
            "--host", "127.0.0.1",
            "--accounts", "10",
            "--balance", "10000",
            "--gas-limit", "30000000",
            "--gas-price", "1000000000",  # 1 gwei
            "--chain-id", "31337"
        ]

        self.anvil_process = subprocess.Popen(
            anvil_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        # Wait for anvil to start
        print("   Waiting for Anvil to start...")
        await asyncio.sleep(3)

        # Connect to the local network
        self.w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

        if not self.w3.is_connected():
            raise RuntimeError("Failed to connect to Anvil testnet")

        print(f"✅ Anvil testnet started (Chain ID: {self.w3.eth.chain_id})")

    def get_deployer_account(self) -> Account:
        """Get deployer account based on network type"""
        if self.network_config["type"] == "local":
            # Use Anvil's first deterministic account
            return Account.from_key(
                "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
            )
        else:
            # Use deployer private key from environment
            deployer_key = os.getenv("DEPLOYER_PRIVATE_KEY")
            if not deployer_key:
                raise ValueError("DEPLOYER_PRIVATE_KEY not set in .env for non-local deployment")
            return Account.from_key(deployer_key)

    def get_test_accounts(self) -> Dict[str, Dict[str, Any]]:
        """Get test accounts based on network type"""
        if self.network_config["type"] == "local":
            # Use Anvil's deterministic accounts
            accounts = [
                {
                    "name": "deployer",
                    "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
                    "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
                },
                {
                    "name": "validator",
                    "private_key": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
                    "address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
                },
                {
                    "name": "client",
                    "private_key": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
                    "address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
                }
            ]
        else:
            # Use environment variables for real networks
            validator_key = os.getenv("VALIDATOR_PRIVATE_KEY")
            client_key = os.getenv("CLIENT_PRIVATE_KEY")

            if not validator_key or not client_key:
                raise ValueError("VALIDATOR_PRIVATE_KEY and CLIENT_PRIVATE_KEY must be set in .env")

            validator_account = Account.from_key(validator_key)
            client_account = Account.from_key(client_key)

            accounts = [
                {
                    "name": "validator",
                    "private_key": validator_key,
                    "address": validator_account.address
                },
                {
                    "name": "client",
                    "private_key": client_key,
                    "address": client_account.address
                }
            ]

        result = {}
        for account in accounts:
            result[account["name"]] = {
                "account": Account.from_key(account["private_key"]),
                "address": account["address"],
                "private_key": account["private_key"]
            }

            # Check balance
            balance = self.w3.eth.get_balance(account["address"])
            print(f"   {account['name']}: {account['address']} ({Web3.from_wei(balance, 'ether')} ETH)")

        return result

    async def deploy_contracts(self):
        """Deploy smart contracts to the configured network"""
        print(f"📄 Deploying contracts to {self.network_config['name']}...")

        # Check if already deployed
        existing = self.load_deployment()
        if existing and existing.get("contracts"):
            print(f"⚠️  Contracts already deployed to {self.network_name}")
            print(f"   Delete {self.get_deployment_path()} to redeploy")
            return existing

        await self.connect_to_network()

        deployer_account = self.get_deployer_account()
        print(f"   Deployer: {deployer_account.address}")

        # Check deployer balance
        balance = self.w3.eth.get_balance(deployer_account.address)
        print(f"   Balance: {Web3.from_wei(balance, 'ether')} ETH")

        if balance < Web3.to_wei(0.01, 'ether'):
            raise RuntimeError("Deployer account has insufficient balance (< 0.01 ETH)")

        # Load contract ABIs and bytecode
        contracts = {}
        contract_files = [
            "IdentityRegistry",
            "ReputationRegistry",
            "ValidationRegistry",
            "VerifiedIdentityRegistry"
        ]

        for contract_name in contract_files:
            artifact_path = self.contracts_dir / "out" / \
                f"{contract_name}.sol" / f"{contract_name}.json"
            with open(artifact_path, 'r') as f:
                artifact = json.load(f)
            contracts[contract_name] = {
                "abi": artifact["abi"],
                "bytecode": artifact["bytecode"]["object"]
            }

        # Deploy contracts in order
        deployed_contracts = {}
        gas_price = self.network_config.get("gas_price") or self.w3.eth.gas_price

        # Initialize nonce counter (fetch once, increment locally to avoid race conditions)
        nonce = self.w3.eth.get_transaction_count(deployer_account.address)

        # 1. Deploy IdentityRegistry
        print("   1. Deploying IdentityRegistry...")
        identity_registry_contract = self.w3.eth.contract(
            abi=contracts["IdentityRegistry"]["abi"],
            bytecode=contracts["IdentityRegistry"]["bytecode"]
        )

        tx = identity_registry_contract.constructor().build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': gas_price,
            'nonce': nonce
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        deployed_contracts["identity_registry"] = receipt.contractAddress
        print(f"      ✅ IdentityRegistry: {receipt.contractAddress}")
        nonce += 1  # Increment nonce for next transaction

        # 2. Deploy ReputationRegistry
        print("   2. Deploying ReputationRegistry...")
        reputation_contract = self.w3.eth.contract(
            abi=contracts["ReputationRegistry"]["abi"],
            bytecode=contracts["ReputationRegistry"]["bytecode"]
        )

        tx = reputation_contract.constructor(deployed_contracts["identity_registry"]).build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': gas_price,
            'nonce': nonce
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        deployed_contracts["reputation_registry"] = receipt.contractAddress
        print(f"      ✅ ReputationRegistry: {receipt.contractAddress}")
        nonce += 1  # Increment nonce for next transaction

        # 3. Deploy ValidationRegistry
        print("   3. Deploying ValidationRegistry...")
        validation_contract = self.w3.eth.contract(
            abi=contracts["ValidationRegistry"]["abi"],
            bytecode=contracts["ValidationRegistry"]["bytecode"]
        )

        tx = validation_contract.constructor(deployed_contracts["identity_registry"]).build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': gas_price,
            'nonce': nonce
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        deployed_contracts["validation_registry"] = receipt.contractAddress
        print(f"      ✅ ValidationRegistry: {receipt.contractAddress}")
        nonce += 1  # Increment nonce for next transaction

        # 4. Deploy VerifiedIdentityRegistry
        print("   4. Deploying VerifiedIdentityRegistry...")
        verified_contract = self.w3.eth.contract(
            abi=contracts["VerifiedIdentityRegistry"]["abi"],
            bytecode=contracts["VerifiedIdentityRegistry"]["bytecode"]
        )

        tx = verified_contract.constructor(
            deployer_account.address,
            deployed_contracts["identity_registry"]
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': gas_price,
            'nonce': nonce
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        deployed_contracts["verified_identity_registry"] = receipt.contractAddress
        print(f"      ✅ VerifiedIdentityRegistry: {receipt.contractAddress}")

        # Save deployment data
        deployment_data = {
            "network": self.network_name,
            "chain_id": self.network_config["chain_id"],
            "rpc_url": self.network_config["rpc_url"],
            "contracts": deployed_contracts,
            "deployer": deployer_account.address,
            "deployed_at": int(time.time())
        }

        self.save_deployment(deployment_data)
        print("✅ Contracts deployed successfully!")

        return deployment_data

    async def setup_agents(self):
        """Setup agents, register to contracts, and configure allowlists"""
        print(f"🤖 Setting up agents on {self.network_config['name']}...")

        # Load deployment data
        deployment = self.load_deployment()
        if not deployment or not deployment.get("contracts"):
            raise RuntimeError(f"No deployment found for {self.network_name}. Run 'deploy' first.")

        # Check if agents already configured
        if deployment.get("agents") and deployment.get("validator_proof"):
            print(f"⚠️  Agents already configured on {self.network_name}")
            print(f"   Delete {self.get_deployment_path()} to reconfigure")
            return deployment

        await self.connect_to_network()
        test_accounts = self.get_test_accounts()

        # Initialize agents
        print("   Initializing agents...")
        from agents.wallet_manager import GenesisWalletManager
        wallet_manager = GenesisWalletManager()
        wallet_manager.w3 = self.w3

        for name, account_data in test_accounts.items():
            if name in ["validator", "client"]:
                wallet_manager.wallets[name] = account_data["account"]

        self.validator_agent = TEEValidatorAgent(
            agent_domain=f"validator.{self.network_name}",
            wallet_address=test_accounts["validator"]["address"],
            wallet_manager=wallet_manager
        )

        self.client_agent = TEEClientAgent(
            agent_domain=f"client.{self.network_name}",
            wallet_address=test_accounts["client"]["address"],
            wallet_manager=wallet_manager
        )

        print("   ✅ Agents initialized")

        # Register agents to IdentityRegistry
        await self._register_agents_to_identity_registry(deployment, test_accounts)

        # Generate validator proof and configure allowlists
        await self._configure_registry_allowlists(deployment, test_accounts)

        # Update deployment with agent info
        deployment["agents"] = {
            "validator": {
                "address": self.validator_agent.address,
                "domain": f"validator.{self.network_name}"
            },
            "client": {
                "address": self.client_agent.address,
                "domain": f"client.{self.network_name}"
            }
        }
        deployment["configured_at"] = int(time.time())

        self.save_deployment(deployment)
        print("✅ Agents setup complete!")

        return deployment

    async def _register_agents_to_identity_registry(self, deployment: Dict, test_accounts: Dict):
        """Register agents to ERC-8004 IdentityRegistry"""
        print("   📋 Registering agents to IdentityRegistry...")

        # Load IdentityRegistry ABI
        abi_path = self.contracts_dir / "out" / \
            "IdentityRegistry.sol" / "IdentityRegistry.json"
        with open(abi_path, 'r') as f:
            contract_abi = json.load(f)["abi"]

        contract = self.w3.eth.contract(
            address=deployment["contracts"]["identity_registry"],
            abi=contract_abi
        )

        gas_price = self.network_config.get("gas_price") or self.w3.eth.gas_price

        # Register validator agent
        validator_account = test_accounts["validator"]["account"]
        validator_nonce = self.w3.eth.get_transaction_count(validator_account.address)
        tx = contract.functions.newAgent(
            f"validator.{self.network_name}",
            self.validator_agent.address
        ).build_transaction({
            'from': validator_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': validator_nonce
        })
        signed_tx = validator_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"      ✅ Validator agent registered (tx: {tx_hash.hex()[:10]}...)")

        # Register client agent
        client_account = test_accounts["client"]["account"]
        client_nonce = self.w3.eth.get_transaction_count(client_account.address)
        tx = contract.functions.newAgent(
            f"client.{self.network_name}",
            self.client_agent.address
        ).build_transaction({
            'from': client_account.address,
            'gas': 200000,
            'gasPrice': gas_price,
            'nonce': client_nonce
        })
        signed_tx = client_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"      ✅ Client agent registered (tx: {tx_hash.hex()[:10]}...)")

    async def _configure_registry_allowlists(self, deployment: Dict, test_accounts: Dict):
        """Configure VerifiedIdentityRegistry with allowlists and validator proof"""
        print("   ⚙️  Configuring VerifiedIdentityRegistry...")

        # Load contract ABI
        abi_path = self.contracts_dir / "out" / \
            "VerifiedIdentityRegistry.sol" / "VerifiedIdentityRegistry.json"
        with open(abi_path, 'r') as f:
            contract_abi = json.load(f)["abi"]

        contract = self.w3.eth.contract(
            address=deployment["contracts"]["verified_identity_registry"],
            abi=contract_abi
        )

        deployer_account = self.get_deployer_account()
        gas_price = self.network_config.get("gas_price") or self.w3.eth.gas_price

        # Initialize nonce counter for deployer
        nonce = self.w3.eth.get_transaction_count(deployer_account.address)

        # Generate and set validator proof
        print("      📝 Setting validator proof...")
        validator_proof = self.validator_agent.generate_validator_proof()

        validator_proof_tuple = (
            validator_proof["agentAddress"],
            validator_proof["agentPubkey"],
            validator_proof["quote"],
            validator_proof["eventlog"]
        )

        tx = contract.functions.setValidatorProof(validator_proof_tuple).build_transaction({
            'from': deployer_account.address,
            'gasPrice': gas_price,
            'nonce': nonce
        })

        gas_estimate = self.w3.eth.estimate_gas(tx)
        tx['gas'] = int(gas_estimate * 1.5)

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status != 1:
            raise RuntimeError("Failed to set validator proof")
        print(f"         ✅ Validator proof set (tx: {tx_hash.hex()[:10]}...)")
        nonce += 1  # Increment nonce for next transaction

        # Configure allowlists based on validator proof
        quote_data = json.loads(validator_proof["quote"])

        # Calculate AggregatedMrs
        if quote_data.get("quote_type") == "real_dstack_tee":
            rtmrs = quote_data.get("rtmrs", {})
            td_report = quote_data.get("td_report", {})

            mrtd = bytes.fromhex(td_report.get("mr_td", "00" * 48))
            rtmr0 = bytes.fromhex(rtmrs.get("0", "00" * 48))
            rtmr1 = bytes.fromhex(rtmrs.get("1", "00" * 48))
            rtmr2 = bytes.fromhex(rtmrs.get("2", "00" * 48))
            rtmr3 = bytes.fromhex(rtmrs.get("3", "00" * 48))

            hasher = hashlib.sha256()
            for mr in [mrtd, rtmr0, rtmr1, rtmr2, rtmr3]:
                hasher.update(mr)

            mr_config_id = bytes.fromhex(td_report.get("mr_config_id", "00" * 48))
            mr_owner = bytes.fromhex(td_report.get("mr_owner", "00" * 48))
            mr_owner_config = bytes.fromhex(td_report.get("mr_owner_config", "00" * 48))

            if (mr_config_id != bytes(48) or mr_owner != bytes(48) or mr_owner_config != bytes(48)):
                hasher.update(mr_config_id)
                hasher.update(mr_owner)
                hasher.update(mr_owner_config)

            mr_hash = hasher.digest()[:32]

            device_id_raw = quote_data["tcb_info"]["device_id"] if isinstance(
                quote_data["tcb_info"]["device_id"], str) else quote_data["tcb_info"]["device_id"]
            device_id_bytes = bytes.fromhex(device_id_raw) if isinstance(
                device_id_raw, str) else device_id_raw
            device_id = Web3.keccak(device_id_bytes)[:32] if len(
                device_id_bytes) > 32 else device_id_bytes.ljust(32, b'\x00')
        else:
            # For mock quotes
            mr_bytes = bytes.fromhex(quote_data["measurement_register"])
            mr_hash = mr_bytes[:32] if len(mr_bytes) >= 32 else mr_bytes.ljust(32, b'\x00')

            device_id_bytes = bytes.fromhex(quote_data["device_id"])
            device_id = device_id_bytes[:32] if len(
                device_id_bytes) >= 32 else device_id_bytes.ljust(32, b'\x00')

        print("      🔧 Configuring validator allowlists...")

        # Allow validator MR
        tx = contract.functions.setValidatorAllowedAggregatedMr(
            mr_hash, True
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print("         ✅ Validator MR allowed")
        nonce += 1  # Increment nonce for next transaction

        # Allow validator device ID
        tx = contract.functions.setValidatorAllowedDeviceId(
            device_id, True
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print("         ✅ Validator device ID allowed")
        nonce += 1  # Increment nonce for next transaction

        # Configure client allowlists
        print("      🔧 Configuring client allowlists...")
        client_quote = self.client_agent.generate_tee_quote()

        if client_quote.get("quote_type") == "real_dstack_tee":
            compose_hash_raw = client_quote["tcb_info"]["compose_hash"] if isinstance(
                client_quote["tcb_info"]["compose_hash"], str) else client_quote["tcb_info"]["compose_hash"]
            compose_hash_bytes = bytes.fromhex(compose_hash_raw) if isinstance(
                compose_hash_raw, str) else compose_hash_raw
            compose_hash = compose_hash_bytes[:32] if len(
                compose_hash_bytes) >= 32 else compose_hash_bytes.ljust(32, b'\x00')
        else:
            compose_hash_bytes = bytes.fromhex(client_quote["compose_hash"])
            compose_hash = compose_hash_bytes[:32] if len(
                compose_hash_bytes) >= 32 else compose_hash_bytes.ljust(32, b'\x00')

        # Allow client compose hash
        tx = contract.functions.setAllowedAgentComposeHash(
            compose_hash, True
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print("         ✅ Client compose hash allowed")

        # Store client quote for validation flow (convert bytes to hex for JSON serialization)
        def make_json_serializable(obj):
            """Recursively convert bytes to hex strings for JSON serialization"""
            if isinstance(obj, bytes):
                return obj.hex()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            else:
                return obj

        deployment["client_quote"] = make_json_serializable(client_quote)
        deployment["validator_proof"] = make_json_serializable(validator_proof)

    async def run_validation(self):
        """Run the TEE validation flow"""
        print(f"🔐 Running validation flow on {self.network_config['name']}...")

        # Load deployment data
        deployment = self.load_deployment()
        if not deployment or not deployment.get("agents"):
            raise RuntimeError(f"Agents not configured for {self.network_name}. Run 'setup-agents' first.")

        await self.connect_to_network()
        test_accounts = self.get_test_accounts()

        # Reinitialize agents
        from agents.wallet_manager import GenesisWalletManager
        wallet_manager = GenesisWalletManager()
        wallet_manager.w3 = self.w3

        for name, account_data in test_accounts.items():
            if name in ["validator", "client"]:
                wallet_manager.wallets[name] = account_data["account"]

        self.validator_agent = TEEValidatorAgent(
            agent_domain=deployment["agents"]["validator"]["domain"],
            wallet_address=deployment["agents"]["validator"]["address"],
            wallet_manager=wallet_manager
        )

        self.client_agent = TEEClientAgent(
            agent_domain=deployment["agents"]["client"]["domain"],
            wallet_address=deployment["agents"]["client"]["address"],
            wallet_manager=wallet_manager
        )

        # Run validation flow
        print("-" * 60)

        # Step 1: Client generates work report
        print("1️⃣  Client generating work report with TEE quote...")
        work_report = {
            "report_id": f"report_{int(time.time())}",
            "agent_address": self.client_agent.address,
            "task_type": "market_analysis",
            "timestamp": int(time.time()),
            "tee_quote": deployment["client_quote"]
        }
        print(f"   📄 Work Report ID: {work_report['report_id']}")
        print(f"   🔐 TEE Quote Type: {work_report['tee_quote']['quote_type']}")

        # Step 2: Client requests validation
        print("\n2️⃣  Client requesting validation from validator...")
        validation_request = {
            "agent_address": self.client_agent.address,
            "quote_data": work_report['tee_quote']
        }

        # Step 3: Validator processes request
        print("\n3️⃣  Validator processing validation request...")
        validation_result = self.validator_agent.handle_agent_validation_request(
            validation_request
        )

        print(f"   📊 Validation Status: {validation_result.status.value}")
        if validation_result.error_message:
            print(f"   ❌ Error: {validation_result.error_message}")

        # Step 4: Update trustlessAgents list
        if validation_result.status.value == "approved":
            print("\n4️⃣  ✅ Validation PASSED - Updating trustlessAgents list...")

            tx_hash = self.validator_agent.update_trustless_agent_status(
                self.client_agent.address, True
            )
            print(f"   📝 Transaction Hash: {tx_hash}")

            # Verify the update
            is_trusted = self.validator_agent.registry_reader.is_trustless_agent(
                self.client_agent.address
            )
            print(f"   ✅ Client trustless status: {is_trusted}")

            if is_trusted:
                print("   🎉 SUCCESS: Client agent is now marked as trustless!")
            else:
                print("   ❌ FAILED: Client agent not marked as trustless")

        else:
            print(f"\n4️⃣  ❌ Validation FAILED: {validation_result.error_message}")
            print("   Trustless status will not be updated")

        # Save validation result
        if "validations" not in deployment:
            deployment["validations"] = []

        deployment["validations"].append({
            "timestamp": int(time.time()),
            "report_id": work_report["report_id"],
            "status": validation_result.status.value,
            "error": validation_result.error_message
        })

        self.save_deployment(deployment)

        return validation_result

    async def cleanup(self):
        """Clean up test resources"""
        if self.anvil_process:
            try:
                os.killpg(os.getpgid(self.anvil_process.pid), signal.SIGTERM)
                self.anvil_process.wait(timeout=5)
                print("   ✅ Anvil process terminated")
            except:
                try:
                    os.killpg(os.getpgid(self.anvil_process.pid), signal.SIGKILL)
                    print("   ⚠️  Anvil process force killed")
                except:
                    print("   ❌ Failed to kill Anvil process")


async def cmd_deploy(args):
    """Deploy contracts command"""
    demo = TEEValidationDemo(args.network)
    try:
        await demo.deploy_contracts()
    finally:
        await demo.cleanup()


async def cmd_setup_agents(args):
    """Setup agents command"""
    demo = TEEValidationDemo(args.network)
    try:
        await demo.setup_agents()
    finally:
        await demo.cleanup()


async def cmd_validate(args):
    """Run validation command"""
    demo = TEEValidationDemo(args.network)
    try:
        await demo.run_validation()
    finally:
        await demo.cleanup()


async def cmd_run_all(args):
    """Run all steps at once"""
    demo = TEEValidationDemo(args.network)
    try:
        print("🚀 Running complete TEE validation demo")
        print("=" * 60)

        await demo.deploy_contracts()
        print()
        await demo.setup_agents()
        print()
        await demo.run_validation()

        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await demo.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="ChaosChain TEE Validation Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy contracts to Base Sepolia
  python tee_validation_demo.py deploy --network base-sepolia

  # Setup agents
  python tee_validation_demo.py setup-agents --network base-sepolia

  # Run validation flow
  python tee_validation_demo.py validate --network base-sepolia

  # Run everything at once on local testnet
  python tee_validation_demo.py run-all --network local
        """
    )

    parser.add_argument(
        "command",
        choices=["deploy", "setup-agents", "validate", "run-all"],
        help="Command to execute"
    )

    parser.add_argument(
        "--network",
        choices=list(NETWORKS.keys()),
        default="local",
        help="Network to use (default: local)"
    )

    args = parser.parse_args()

    # Validate environment
    if not os.getenv('DSTACK_SIMULATOR_ENDPOINT'):
        print("❌ DSTACK_SIMULATOR_ENDPOINT not set!")
        print("   Please ensure dstack simulator is running")
        return 1

    # Check Foundry tools
    required_tools = ["forge", "cast"]
    if args.network == "local":
        required_tools.append("anvil")

    for tool in required_tools:
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            print(f"❌ {tool} not found! Please install Foundry")
            return 1

    # Execute command
    commands = {
        "deploy": cmd_deploy,
        "setup-agents": cmd_setup_agents,
        "validate": cmd_validate,
        "run-all": cmd_run_all
    }

    try:
        asyncio.run(commands[args.command](args))
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())