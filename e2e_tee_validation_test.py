#!/usr/bin/env python3
"""
Comprehensive End-to-End TEE Validation Test

This script runs a complete E2E test covering:
1. Local testnet setup with Anvil and smart contract deployment
2. TEE validator and client agent initialization and registration
3. VerifiedIdentityRegistry configuration with allowlists
4. TEE quote generation and validation flow
5. TrustlessAgents list updates based on validation results

Requirements:
- dstack simulator running with DSTACK_SIMULATOR_ENDPOINT set
- Foundry installed (anvil, forge, cast)
- Python dependencies from requirements.txt
"""

from agents.chaoschain_agent_sdk import ChaosChainAgentSDK
from agents.base_agent_genesis import GenesisBaseAgent
from agents.tee_client_agent import TEEClientAgent
from agents.tee_validator_agent import TEEValidatorAgent
import asyncio
import hashlib
import json
import os
import subprocess
import time
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from web3 import Web3, EthereumTesterProvider
from eth_account import Account

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))


class E2ETEEValidationTest:
    """End-to-End TEE Validation Test Suite"""

    def __init__(self):
        """Initialize the test suite"""
        self.anvil_process = None
        self.test_accounts = {}
        self.contract_addresses = {}
        self.w3 = None
        self.validator_agent = None
        self.client_agent = None
        self.base_dir = Path(__file__).parent
        self.contracts_dir = self.base_dir / "contracts"

    async def setup_test_environment(self):
        """Set up complete test environment"""
        print("🚀 Setting up E2E TEE Validation Test Environment")
        print("=" * 60)

        # Configure environment for local network
        os.environ['NETWORK'] = 'local'
        os.environ['LOCAL_RPC_URL'] = 'http://127.0.0.1:8545'
        os.environ['LOCAL_CHAIN_ID'] = '31337'

        # Step 1: Start local testnet
        await self.start_anvil_testnet()

        # Step 2: Deploy smart contracts
        await self.deploy_contracts()

        # Step 3: Initialize test accounts and agents
        await self.setup_test_accounts()
        await self.initialize_agents()

        # Step 4: Configure contract allowlists
        await self.configure_registry_allowlists()

        print("✅ Test environment setup complete!")

    async def start_anvil_testnet(self):
        """Start Anvil local testnet"""
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

    async def deploy_contracts(self):
        """Deploy smart contracts using direct Web3 deployment"""
        print("📄 Deploying smart contracts...")

        deployer_account = Account.from_key(
            "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")

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

        # 1. Deploy IdentityRegistry first (no dependencies)
        print("   1. Deploying IdentityRegistry...")
        identity_registry_contract = self.w3.eth.contract(
            abi=contracts["IdentityRegistry"]["abi"],
            bytecode=contracts["IdentityRegistry"]["bytecode"]
        )

        tx = identity_registry_contract.constructor().build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        deployed_contracts["identity_registry"] = receipt.contractAddress
        print(
            f"      ✅ IdentityRegistry deployed at: {receipt.contractAddress}")

        # 2. Deploy ReputationRegistry (depends on IdentityRegistry)
        print("   2. Deploying ReputationRegistry...")
        reputation_contract = self.w3.eth.contract(
            abi=contracts["ReputationRegistry"]["abi"],
            bytecode=contracts["ReputationRegistry"]["bytecode"]
        )

        tx = reputation_contract.constructor(deployed_contracts["identity_registry"]).build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        deployed_contracts["reputation_registry"] = receipt.contractAddress
        print(
            f"      ✅ ReputationRegistry deployed at: {receipt.contractAddress}")

        # 3. Deploy ValidationRegistry (depends on IdentityRegistry)
        print("   3. Deploying ValidationRegistry...")
        validation_contract = self.w3.eth.contract(
            abi=contracts["ValidationRegistry"]["abi"],
            bytecode=contracts["ValidationRegistry"]["bytecode"]
        )

        tx = validation_contract.constructor(deployed_contracts["identity_registry"]).build_transaction({
            'from': deployer_account.address,
            'gas': 3000000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        deployed_contracts["validation_registry"] = receipt.contractAddress
        print(
            f"      ✅ ValidationRegistry deployed at: {receipt.contractAddress}")

        # 4. Deploy VerifiedIdentityRegistry (depends on IdentityRegistry)
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
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        deployed_contracts["verified_identity_registry"] = receipt.contractAddress
        print(
            f"      ✅ VerifiedIdentityRegistry deployed at: {receipt.contractAddress}")

        self.contract_addresses = deployed_contracts

        # Create deployment file for agents to use
        self._create_deployment_file()

        print("✅ Contracts deployed successfully!")

    def _create_deployment_file(self):
        """Create deployment file for agent consumption"""
        deployment_data = {
            "network": "local",
            "chain_id": 31337,
            "rpc_url": "http://127.0.0.1:8545",
            "contracts": self.contract_addresses,
            "timestamp": int(time.time())
        }

        deployment_path = self.base_dir / "deployment.json"
        with open(deployment_path, 'w') as f:
            json.dump(deployment_data, f, indent=2)

        print(f"   Created deployment file: {deployment_path}")

    async def setup_test_accounts(self):
        """Set up test accounts from Anvil"""
        print("👤 Setting up test accounts...")

        # Use anvil's deterministic accounts
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

        for account in accounts:
            self.test_accounts[account["name"]] = {
                "account": Account.from_key(account["private_key"]),
                "address": account["address"],
                "private_key": account["private_key"]
            }

            # Check balance
            balance = self.w3.eth.get_balance(account["address"])
            print(
                f"   {account['name']}: {account['address']} ({Web3.from_wei(balance, 'ether')} ETH)")

        print("✅ Test accounts ready")

    async def initialize_agents(self):
        """Initialize TEE validator and client agents"""
        print("🤖 Initializing TEE agents...")

        # Create wallet manager for agents
        from agents.wallet_manager import GenesisWalletManager
        wallet_manager = GenesisWalletManager()

        # Override wallet manager's w3 to use our local connection
        wallet_manager.w3 = self.w3

        # Add test accounts to wallet manager
        for name, account_data in self.test_accounts.items():
            if name in ["validator", "client"]:
                wallet_manager.wallets[name] = account_data["account"]

        # Initialize validator agent with local network
        self.validator_agent = TEEValidatorAgent(
            agent_domain=f"validator.testnet.local",
            wallet_address=self.test_accounts["validator"]["address"],
            wallet_manager=wallet_manager
        )

        # Initialize client agent with local network
        self.client_agent = TEEClientAgent(
            agent_domain=f"client.testnet.local",
            wallet_address=self.test_accounts["client"]["address"],
            wallet_manager=wallet_manager
        )

        print("   ✅ TEE Validator Agent initialized")
        print("   ✅ TEE Client Agent initialized")

    async def configure_registry_allowlists(self):
        """Configure VerifiedIdentityRegistry with allowlists and validator proof"""
        print("⚙️  Configuring VerifiedIdentityRegistry...")

        # Load contract ABI
        abi_path = self.contracts_dir / "out" / \
            "VerifiedIdentityRegistry.sol" / "VerifiedIdentityRegistry.json"
        with open(abi_path, 'r') as f:
            contract_abi = json.load(f)["abi"]

        contract = self.w3.eth.contract(
            address=self.contract_addresses["verified_identity_registry"],
            abi=contract_abi
        )

        deployer_account = self.test_accounts["deployer"]["account"]

        # Step 1: Generate and set validator proof
        print("   📝 Setting validator proof...")
        validator_proof = self.validator_agent.generate_validator_proof()

        # Create proper ValidatorProof tuple
        validator_proof_tuple = (
            validator_proof["agentAddress"],
            validator_proof["agentPubkey"],
            validator_proof["quote"],
            validator_proof["eventlog"]
        )

        # Check current nonce and gas price
        current_nonce = self.w3.eth.get_transaction_count(
            deployer_account.address)
        print(f"      🔍 Current nonce: {current_nonce}")

        tx = contract.functions.setValidatorProof(validator_proof_tuple).build_transaction({
            'from': deployer_account.address,
            'nonce': current_nonce
        })

        # Let Web3 estimate gas
        try:
            gas_estimate = self.w3.eth.estimate_gas(tx)
            tx['gas'] = gas_estimate * 2  # Double the estimate for safety
            print(f"      ⛽ Gas estimate: {gas_estimate}, using: {tx['gas']}")
        except Exception as e:
            print(f"      ⚠️  Gas estimation failed: {e}, using 500000")
            tx['gas'] = 500000

        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"      📝 Transaction sent: {tx_hash.hex()}")

        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=30)
            if receipt.status != 1:
                raise RuntimeError("Failed to set validator proof")
            print("      ✅ Validator proof set")
        except Exception as e:
            print(f"      ❌ Transaction failed or timed out: {e}")
            # Check if transaction is pending
            try:
                tx_info = self.w3.eth.get_transaction(tx_hash)
                print(f"      🔍 Transaction info: {tx_info}")
            except:
                print("      🔍 Transaction not found in mempool")
            raise

        # Step 2: Configure allowlists based on validator proof
        quote_data = json.loads(validator_proof["quote"])

        # Calculate AggregatedMrs following dstack implementation
        if quote_data.get("quote_type") == "real_dstack_tee":
            rtmrs = quote_data.get("rtmrs", {})
            td_report = quote_data.get("td_report", {})

            # Extract all measurement registers (following dstack pattern)
            # TODO.shelven: fix this, mr_td is not available in simulator
            mrtd = bytes.fromhex(td_report.get("mr_td", "00" * 48))
            rtmr0 = bytes.fromhex(rtmrs.get("0", "00" * 48))
            rtmr1 = bytes.fromhex(rtmrs.get("1", "00" * 48))
            rtmr2 = bytes.fromhex(rtmrs.get("2", "00" * 48))
            rtmr3 = bytes.fromhex(rtmrs.get("3", "00" * 48))

            # Calculate AggregatedMrs using SHA256 hash of all MRs (as per dstack)
            hasher = hashlib.sha256()
            for mr in [mrtd, rtmr0, rtmr1, rtmr2, rtmr3]:
                hasher.update(mr)

            # Check for optional MRs (for backward compatibility)
            mr_config_id = bytes.fromhex(
                td_report.get("mr_config_id", "00" * 48))
            mr_owner = bytes.fromhex(td_report.get("mr_owner", "00" * 48))
            mr_owner_config = bytes.fromhex(
                td_report.get("mr_owner_config", "00" * 48))

            if (mr_config_id != bytes(48) or mr_owner != bytes(48) or mr_owner_config != bytes(48)):
                hasher.update(mr_config_id)
                hasher.update(mr_owner)
                hasher.update(mr_owner_config)

            mr_hash = hasher.digest()[:32]  # Take first 32 bytes for bytes32
            print(f"      🔍 AggregatedMrs (MRTD+RTMR0-3): {mr_hash.hex()}")

            device_id_raw = quote_data["tcb_info"]["device_id"] if isinstance(
                quote_data["tcb_info"]["device_id"], str) else quote_data["tcb_info"]["device_id"]
            device_id_bytes = bytes.fromhex(device_id_raw) if isinstance(
                device_id_raw, str) else device_id_raw
            device_id = Web3.keccak(device_id_bytes)[:32] if len(
                device_id_bytes) > 32 else device_id_bytes.ljust(32, b'\x00')
        else:
            # For mock quotes - use simple approach
            mr_bytes = bytes.fromhex(quote_data["measurement_register"])
            mr_hash = mr_bytes[:32] if len(
                mr_bytes) >= 32 else mr_bytes.ljust(32, b'\x00')

            device_id_bytes = bytes.fromhex(quote_data["device_id"])
            device_id = device_id_bytes[:32] if len(
                device_id_bytes) >= 32 else device_id_bytes.ljust(32, b'\x00')

        print("   🔧 Configuring validator allowlists...")

        # Allow validator MR
        tx = contract.functions.setValidatorAllowedAggregatedMr(
            mr_hash, True
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 100000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print("      ✅ Validator MR allowed")

        # Allow validator device ID
        tx = contract.functions.setValidatorAllowedDeviceId(
            device_id, True
        ).build_transaction({
            'from': deployer_account.address,
            'gas': 100000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print("      ✅ Validator device ID allowed")

        # Step 3: Generate client quote and allow client compose hash + MR
        print("   🔧 Configuring client allowlists...")
        client_quote = self.client_agent.generate_tee_quote()
        # Store the client quote for later use in validation flow
        self.client_test_quote = client_quote

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
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(deployer_account.address)
        })
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print("      ✅ Client compose hash allowed")

        print("✅ Registry configuration complete")

    async def register_agents_to_identity_registry(self):
        """Register agents to ERC-8004 IdentityRegistry"""
        print("📋 Registering agents to IdentityRegistry...")

        # Load IdentityRegistry ABI
        abi_path = self.contracts_dir / "out" / \
            "IdentityRegistry.sol" / "IdentityRegistry.json"
        with open(abi_path, 'r') as f:
            contract_abi = json.load(f)["abi"]

        contract = self.w3.eth.contract(
            address=self.contract_addresses["identity_registry"],
            abi=contract_abi
        )

        # Register validator agent
        validator_account = self.test_accounts["validator"]["account"]
        tx = contract.functions.newAgent(
            "validator.testnet.local",
            self.validator_agent.address
        ).build_transaction({
            'from': validator_account.address,
            'gas': 200000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(validator_account.address)
        })
        signed_tx = validator_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print(f"   ✅ Validator agent registered (Agent ID: {receipt.logs})")

        # Register client agent
        client_account = self.test_accounts["client"]["account"]
        tx = contract.functions.newAgent(
            "client.testnet.local",
            self.client_agent.address
        ).build_transaction({
            'from': client_account.address,
            'gas': 200000,
            'gasPrice': 1000000000,  # 1 gwei for local testnet
            'nonce': self.w3.eth.get_transaction_count(client_account.address)
        })
        signed_tx = client_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        print(f"   ✅ Client agent registered (Agent ID: {receipt.logs})")

    async def run_tee_validation_flow(self):
        """Run the complete TEE validation flow"""
        print("🔐 Running TEE validation flow...")
        print("-" * 40)

        # Step 1: Client generates work report with TEE quote (use stored quote for consistency)
        print("1️⃣  Client generating work report with TEE quote...")
        work_report = {
            "report_id": f"report_{int(time.time())}",
            "agent_address": self.client_agent.address,
            "task_type": "market_analysis",
            "timestamp": int(time.time()),
            # Use the same quote we configured allowlists for
            "tee_quote": self.client_test_quote
        }
        print(f"   📄 Work Report ID: {work_report['report_id']}")
        print(f"   🔐 TEE Quote Type: {work_report['tee_quote']['quote_type']}")

        # Step 2: Client requests validation from validator
        print("\n2️⃣  Client requesting validation from validator...")
        validation_request = {
            "agent_address": self.client_agent.address,
            "quote_data": work_report['tee_quote']
        }

        # Step 3: Validator processes validation request
        print("\n3️⃣  Validator processing validation request...")
        validation_result = self.validator_agent.handle_agent_validation_request(
            validation_request)

        print(f"   📊 Validation Status: {validation_result.status.value}")
        if validation_result.error_message:
            print(f"   ❌ Error: {validation_result.error_message}")

        # Step 4: If validation passed, update trustlessAgents list
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
            print(f"   ✅ Client agent trustless status: {is_trusted}")

            if is_trusted:
                print("   🎉 SUCCESS: Client agent is now marked as trustless!")
            else:
                print("   ❌ FAILED: Client agent not marked as trustless")

        else:
            print(
                f"\n4️⃣  ❌ Validation FAILED: {validation_result.error_message}")
            print("   Trustless status will not be updated")

        return validation_result

    async def verify_test_results(self):
        """Verify the complete test results"""
        print("\n🔍 Verifying test results...")
        print("-" * 30)

        # Check validator registration status
        validator_status = self.validator_agent.check_validator_status()
        print(
            f"✅ Registry Available: {validator_status['registry_available']}")
        print(
            f"✅ Validator Proof Available: {validator_status['validator_proof_available']}")

        # Check if client is marked as trustless
        is_client_trusted = self.validator_agent.registry_reader.is_trustless_agent(
            self.client_agent.address
        )
        print(f"✅ Client Trusted Status: {is_client_trusted}")

        # Check validator address matches
        validator_address = self.validator_agent.registry_reader.get_validator_address()
        print(
            f"✅ Validator Address Match: {validator_address == self.validator_agent.address}")

        return {
            "registry_available": validator_status['registry_available'],
            "validator_proof_available": validator_status['validator_proof_available'],
            "client_trusted": is_client_trusted,
            "validator_address_match": validator_address == self.validator_agent.address
        }

    async def cleanup(self):
        """Clean up test resources"""
        print("\n🧹 Cleaning up test environment...")

        if self.anvil_process:
            try:
                # Kill the process group to ensure all child processes are terminated
                os.killpg(os.getpgid(self.anvil_process.pid), signal.SIGTERM)
                self.anvil_process.wait(timeout=5)
                print("   ✅ Anvil process terminated")
            except:
                try:
                    os.killpg(os.getpgid(self.anvil_process.pid),
                              signal.SIGKILL)
                    print("   ⚠️  Anvil process force killed")
                except:
                    print("   ❌ Failed to kill Anvil process")

        # Clean up deployment file
        deployment_path = self.base_dir / "deployment.json"
        if deployment_path.exists():
            deployment_path.unlink()
            print("   ✅ Deployment file removed")

    async def run_complete_test(self):
        """Run the complete E2E test"""
        try:
            print("🚀 ChaosChain TEE Validation E2E Test")
            print("=" * 50)
            print(
                f"DSTACK_SIMULATOR_ENDPOINT: {os.getenv('DSTACK_SIMULATOR_ENDPOINT', 'Not set')}")
            print()

            # Setup environment
            await self.setup_test_environment()

            # Register agents
            await self.register_agents_to_identity_registry()

            # Run validation flow
            validation_result = await self.run_tee_validation_flow()

            # Verify results
            test_results = await self.verify_test_results()

            print("\n" + "=" * 50)
            print("🏁 TEST SUMMARY")
            print("=" * 50)

            success = (
                test_results["registry_available"] and
                test_results["validator_proof_available"] and
                test_results["client_trusted"] and
                test_results["validator_address_match"] and
                validation_result.status.value == "approved"
            )

            if success:
                print("🎉 ALL TESTS PASSED!")
                print("✅ TEE Validation E2E flow working correctly")
            else:
                print("❌ SOME TESTS FAILED!")
                print("Please check the logs above for details")

            return success

        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    # Validate environment
    if not os.getenv('DSTACK_SIMULATOR_ENDPOINT'):
        print("❌ DSTACK_SIMULATOR_ENDPOINT not set!")
        print("   Please ensure dstack simulator is running and endpoint is set")
        return 1

    # Check required tools
    required_tools = ["anvil", "forge", "cast"]
    for tool in required_tools:
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            print(f"❌ {tool} not found! Please install Foundry")
            return 1

    test_suite = E2ETEEValidationTest()
    success = await test_suite.run_complete_test()

    return 0 if success else 1


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n🛑 Test interrupted by user")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
