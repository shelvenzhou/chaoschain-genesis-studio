# TEE Validation Demo

A production-ready demonstration system for TEE-based agent validation with multi-chain support and separated deployment steps for customer showcases.

## Overview

The `tee_validation_demo.py` script demonstrates ChaosChain's TEE validation capabilities through a complete workflow:

1. **Deploy Contracts** - Deploy ERC-8004 registries to any supported network
2. **Setup Agents** - Initialize validator and client agents, generate TEE proofs, configure allowlists
3. **Run Validation** - Execute the complete TEE validation flow and verify trustless status

## Supported Networks

- **local** - Anvil local testnet (auto-started)
- **base-sepolia** - Base Sepolia testnet (recommended for demos)
- **sepolia** - Ethereum Sepolia testnet
- **optimism-sepolia** - Optimism Sepolia testnet

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Foundry

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

### 3. (Optional) Setup dstack Simulator

```bash
# Start dstack simulator (required for TEE proof generation)
export DSTACK_SIMULATOR_ENDPOINT=/path/to/your/dstack.sock
```

### 4. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

For **local network** testing:

- No additional configuration needed
- Uses Anvil's deterministic accounts

For **testnet/mainnet** deployment:

```bash
# In .env file (add these additional variables):
DEPLOYER_PRIVATE_KEY=0xYOUR_DEPLOYER_KEY
VALIDATOR_PRIVATE_KEY=0xYOUR_VALIDATOR_KEY
CLIENT_PRIVATE_KEY=0xYOUR_CLIENT_KEY
```

**Note**: The script uses existing environment variables from `.env.example`:

- `BASE_SEPOLIA_RPC_URL` for Base Sepolia
- `SEPOLIA_RPC_URL` for Ethereum Sepolia
- `OPTIMISM_SEPOLIA_RPC_URL` for Optimism Sepolia

**Important**: Ensure all accounts have sufficient ETH for gas fees:

- Deployer: ~0.05 ETH
- Validator: ~0.01 ETH
- Client: ~0.01 ETH

## Usage

### Quick Start (All-in-One)

Run the complete demo on local testnet:

```bash
python tee_validation_demo.py run-all --network local
```

### Customer Showcase (Separated Steps)

For customer demonstrations, run each step separately to explain the architecture:

#### Step 1: Deploy Smart Contracts

Deploy ERC-8004 registries to Base Sepolia:

```bash
python tee_validation_demo.py deploy --network base-sepolia
```

**What happens:**

- Connects to Base Sepolia network
- Deploys 4 smart contracts:
  - `IdentityRegistry` - Agent identity management
  - `ReputationRegistry` - On-chain reputation tracking
  - `ValidationRegistry` - Validation records
  - `VerifiedIdentityRegistry` - TEE-verified identity management
- Saves deployment info to `deployments/base-sepolia.json`

**Demo talking points:**

- Show the deployed contract addresses on block explorer
- Explain ERC-8004 standard for agent identity
- Highlight the VerifiedIdentityRegistry's TEE integration

#### Step 2: Setup Agents

Initialize agents and configure TEE allowlists:

```bash
python tee_validation_demo.py setup-agents --network base-sepolia
```

**What happens:**

- Initializes validator and client agents
- Registers agents to IdentityRegistry
- Generates TEE proof from validator
- Configures allowlists in VerifiedIdentityRegistry:
  - Validator's measurement registers (MR)
  - Validator's device ID
  - Client's compose hash
- Stores agent info and TEE proofs in deployment file

**Demo talking points:**

- Show the TEE quote structure (measurement registers, device IDs)
- Explain how allowlists enforce trusted execution environments
- Highlight the cryptographic verification of TEE proofs

#### Step 3: Run Validation Flow

Execute the complete TEE validation workflow:

```bash
python tee_validation_demo.py validate --network base-sepolia
```

**What happens:**

1. Client generates work report with TEE quote
2. Client requests validation from validator
3. Validator verifies:
   - TEE quote authenticity
   - Measurement registers match allowlist
   - Device ID is approved
4. If validated, update `trustlessAgents` list on-chain
5. Verify client's trustless status

**Demo talking points:**

- Show the validation flow in real-time
- Explain how TEE quotes prove code integrity
- Demonstrate on-chain verification of trustless status
- View the transaction on block explorer

## Deployment Files

Each network deployment creates a JSON file in `deployments/{network}.json`:

```json
{
  "network": "base-sepolia",
  "chain_id": 84532,
  "rpc_url": "https://sepolia.base.org",
  "contracts": {
    "identity_registry": "0x...",
    "reputation_registry": "0x...",
    "validation_registry": "0x...",
    "verified_identity_registry": "0x..."
  },
  "deployer": "0x...",
  "deployed_at": 1234567890,
  "agents": {
    "validator": {
      "address": "0x...",
      "domain": "validator.base-sepolia"
    },
    "client": {
      "address": "0x...",
      "domain": "client.base-sepolia"
    }
  },
  "validator_proof": {...},
  "client_quote": {...},
  "configured_at": 1234567890,
  "validations": [
    {
      "timestamp": 1234567890,
      "report_id": "report_1234567890",
      "status": "approved",
      "error": null
    }
  ]
}
```

## Architecture

### Multi-Chain Support

The demo uses a network configuration system that supports:

```python
NETWORKS = {
    "local": {"rpc_url": "http://127.0.0.1:8545", "chain_id": 31337},
    "base-sepolia": {"rpc_url": env.BASE_SEPOLIA_RPC, "chain_id": 84532},
    "base": {"rpc_url": env.BASE_RPC, "chain_id": 8453}
}
```

### State Persistence

Each step saves state to `deployments/{network}.json`, allowing:

- **Idempotent operations** - Can rerun steps safely
- **Pauseable demos** - Stop between steps to explain
- **Multiple validations** - Run validation multiple times without redeployment

### TEE Integration

The demo integrates with dstack SDK for TEE proof generation:

- Validator generates TEE quote with measurement registers
- Client generates TEE quote with compose hash
- VerifiedIdentityRegistry enforces allowlists on-chain

## Troubleshooting

### "DSTACK_SIMULATOR_ENDPOINT not set"

Ensure dstack simulator is running and endpoint is configured:

```bash
export DSTACK_SIMULATOR_ENDPOINT=/path/to/dstack.sock
```

### "Failed to connect to network"

Check RPC URL in `.env` file:

```bash
# Verify connection
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  https://sepolia.base.org
```

### "Insufficient balance"

Fund your accounts with testnet ETH:

- Base Sepolia: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet
- Ethereum Sepolia: https://sepoliafaucet.com/

### "Contracts already deployed"

If you want to redeploy, delete the deployment file:

```bash
rm deployments/base-sepolia.json
```

## Advanced Usage

### Deploy to Multiple Networks

Deploy to different networks for comparison:

```bash
# Deploy to Base Sepolia
python tee_validation_demo.py deploy --network base-sepolia

# Deploy to Ethereum Sepolia
python tee_validation_demo.py deploy --network sepolia
```

### Run Multiple Validations

After setup, you can run validation multiple times:

```bash
# First validation
python tee_validation_demo.py validate --network base-sepolia

# Second validation (uses same deployment)
python tee_validation_demo.py validate --network base-sepolia
```

Each validation is recorded in the deployment file's `validations` array.

## Security Considerations

### Private Key Management

- **Never commit** private keys to git
- Use hardware wallets for mainnet deployments
- Rotate keys regularly for testnets
- Use separate keys for different environments

### Network Security

- **Local**: Safe for development, no real funds
- **Testnet**: Safe for demos, use testnet ETH only
- **Mainnet**: Requires audit, security review, and insurance

### TEE Security

- Validator proofs enforce trusted execution
- Allowlists prevent unauthorized TEE environments
- Measurement registers ensure code integrity
- Device IDs prevent hardware tampering

## Next Steps

After running the demo:

1. **Explore Contracts** - View deployed contracts on block explorer
2. **Modify Agents** - Create custom agent implementations
3. **Add Validation Logic** - Implement domain-specific validation rules
4. **Build Applications** - Use the TEE validation system in production apps

## Support

For issues or questions:

- GitHub Issues: https://github.com/chaoschain/genesis-studio/issues
- Documentation: See [TEE_VALIDATOR_IMPLEMENTATION.md](./TEE_VALIDATOR_IMPLEMENTATION.md)
- Discord: https://discord.gg/chaoschain
