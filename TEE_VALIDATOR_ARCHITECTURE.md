# TEE Validator Architecture & Flow

This document provides a comprehensive visualization of the ChaosChain TEE Validation system architecture and workflow.

## Contract Architecture

```mermaid
graph TB
    subgraph "Core ERC-8004 Contracts"
        IR[IdentityRegistry<br/>---<br/>Agent Registration<br/>Domain → Address mapping]
        RR[ReputationRegistry<br/>---<br/>Feedback Authorization<br/>Client ↔ Server feedback]
        VR[ValidationRegistry<br/>---<br/>Validation Requests<br/>Request/Response tracking]
    end

    subgraph "TEE Extension"
        VIR[VerifiedIdentityRegistry<br/>---<br/>TEE Validation<br/>Validator Proof<br/>Allowlists<br/>trustlessAgents mapping]
    end

    RR -.->|references| IR
    VR -.->|references| IR
    VIR -.->|references| IR
    VIR -.->|Owner manages| VIR

    style IR fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    style RR fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    style VR fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style VIR fill:#e8f5e9,stroke:#1b5e20,stroke-width:3px
```

**Key Relationships:**
- **IdentityRegistry**: Base registry - all other contracts reference it for agent lookups
- **ReputationRegistry**: Manages feedback authorization between agents
- **ValidationRegistry**: Handles validation requests and responses
- **VerifiedIdentityRegistry**: TEE-focused contract managing validator proofs and trustless agent registry

---

## TEE Validation Demo Flow

### Overview: Three-Phase Process

```mermaid
sequenceDiagram
    autonumber

    participant Deployer
    participant Blockchain
    participant Validator as Validator Agent<br/>(TEE)
    participant Client as Client Agent<br/>(TEE)
    participant dstack as dstack<br/>(TEE SDK)

    rect rgb(200, 220, 255)
    Note over Deployer,Blockchain: PHASE 1: Deploy Contracts
    Deployer->>Blockchain: Deploy IdentityRegistry
    Deployer->>Blockchain: Deploy ReputationRegistry(IdentityRegistry)
    Deployer->>Blockchain: Deploy ValidationRegistry(IdentityRegistry)
    Deployer->>Blockchain: Deploy VerifiedIdentityRegistry(owner, IdentityRegistry)
    Note over Blockchain: All contracts deployed<br/>Saved to deployments/{network}.json
    end

    rect rgb(220, 255, 220)
    Note over Validator,Blockchain: PHASE 2: Setup Agents
    Validator->>Blockchain: Register to IdentityRegistry.newAgent()
    Client->>Blockchain: Register to IdentityRegistry.newAgent()

    Validator->>dstack: Generate TEE Quote
    dstack-->>Validator: TEE Quote (RTMR, Device ID, etc.)
    Validator->>Validator: Create ValidatorProof

    Deployer->>Blockchain: setValidatorProof(ValidatorProof)
    Deployer->>Blockchain: setValidatorAllowedAggregatedMr(mrHash, true)
    Deployer->>Blockchain: setValidatorAllowedDeviceId(deviceId, true)

    Client->>dstack: Generate TEE Quote
    dstack-->>Client: TEE Quote (compose_hash, etc.)
    Deployer->>Blockchain: setAllowedAgentComposeHash(composeHash, true)

    Note over Blockchain: Allowlists configured<br/>System ready for validation
    end

    rect rgb(255, 240, 220)
    Note over Client,Blockchain: PHASE 3: Validation Flow
    Client->>Client: Generate work report + TEE quote
    Client->>Validator: Request validation (agent_address, quote_data)

    Validator->>Validator: Parse TEE quote
    Validator->>Blockchain: Check isAllowedAgentComposeHash()
    Validator->>Blockchain: Check isValidatorAllowedDeviceId()
    Validator->>Blockchain: Check isValidatorAllowedAggregatedMr()

    alt All checks pass
        Validator->>Validator: ValidationResult = APPROVED
        Validator->>Blockchain: updateTrustlessAgent(client, true)
        Note over Blockchain: trustlessAgents[client] = true
        Validator-->>Client: ✅ Validation APPROVED
    else Any check fails
        Validator->>Validator: ValidationResult = REJECTED
        Validator-->>Client: ❌ Validation REJECTED
    end
    end
```

---

## Detailed Component Interactions

### Contract Relationship Details

```mermaid
classDiagram
    class IdentityRegistry {
        +newAgent(domain, address)
        +updateAgent(id, domain, address)
        +getAgent(id)
        +resolveByDomain(domain)
        +resolveByAddress(address)
    }

    class ReputationRegistry {
        +IIdentityRegistry identityRegistry
        +acceptFeedback(clientId, serverId)
        +isFeedbackAuthorized(clientId, serverId)
    }

    class ValidationRegistry {
        +IIdentityRegistry identityRegistry
        +validationRequest(validatorId, serverId, dataHash)
        +validationResponse(dataHash, response)
        +getValidationRequest(dataHash)
    }

    class VerifiedIdentityRegistry {
        +IIdentityRegistry identityRegistry
        +ValidatorProof validatorProof
        +mapping validatorAllowedAggregatedMrs
        +mapping validatorAllowedDeviceIds
        +mapping allowedAgentComposeHashes
        +mapping trustlessAgents
        ---
        +setValidatorProof(proof)
        +setValidatorAllowedAggregatedMr(mr, allowed)
        +setValidatorAllowedDeviceId(deviceId, allowed)
        +setAllowedAgentComposeHash(hash, allowed)
        +updateTrustlessAgent(agent, trusted) onlyValidator
        ---
        +isTrustlessAgent(agent)
        +isAllowedAgentComposeHash(hash)
        +isValidatorAllowedDeviceId(deviceId)
        +isValidatorAllowedAggregatedMr(mr)
    }

    ReputationRegistry --> IdentityRegistry : references
    ValidationRegistry --> IdentityRegistry : references
    VerifiedIdentityRegistry --> IdentityRegistry : references
```

---

## TEE Components Architecture

```mermaid
graph LR
    subgraph "Validator Agent (TEE)"
        VA[TEEValidatorAgent]
        VPS[ValidatorProofService]
        RR[RegistryReader]
        AVS[A2AVerificationService]

        VA --> VPS
        VA --> RR
        VA --> AVS
        AVS --> RR
        AVS --> VPS
    end

    subgraph "Client Agent (TEE)"
        CA[TEEClientAgent]
    end

    subgraph "dstack TEE SDK"
        DS[dstack simulator]
    end

    subgraph "Blockchain"
        VIR_BC[VerifiedIdentityRegistry]
    end

    VPS -->|generate_quote| DS
    CA -->|generate_quote| DS
    RR -->|read state| VIR_BC
    AVS -->|verify_quote| VPS
    VA -->|updateTrustlessAgent| VIR_BC

    style VA fill:#b3e5fc,stroke:#01579b,stroke-width:3px
    style CA fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    style DS fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style VIR_BC fill:#ffccbc,stroke:#bf360c,stroke-width:2px
```

---

## Validation Decision Logic

```mermaid
flowchart TD
    Start([Client sends<br/>validation request]) --> Parse[Validator parses<br/>TEE quote]
    Parse --> Extract[Extract:<br/>- compose_hash<br/>- device_id<br/>- aggregated_mr]

    Extract --> Check1{Is compose_hash<br/>allowed?}
    Check1 -->|No| Reject1[REJECTED:<br/>Compose hash not allowed]
    Check1 -->|Yes| Check2{Is device_id<br/>allowed?}

    Check2 -->|No| Reject2[REJECTED:<br/>Device ID not allowed]
    Check2 -->|Yes| Check3{Is aggregated_mr<br/>allowed?}

    Check3 -->|No| Reject3[REJECTED:<br/>MR not allowed]
    Check3 -->|Yes| Approve[APPROVED]

    Approve --> Update["Update on-chain:<br/>trustlessAgents(client) = true"]
    Update --> Success([✅ Client marked<br/>as trustless])

    Reject1 --> Fail([❌ Validation failed])
    Reject2 --> Fail
    Reject3 --> Fail

    style Start fill:#e3f2fd,stroke:#1565c0
    style Success fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
    style Fail fill:#ffcdd2,stroke:#c62828,stroke-width:3px
    style Approve fill:#a5d6a7,stroke:#388e3c
    style Reject1 fill:#ef9a9a,stroke:#c62828
    style Reject2 fill:#ef9a9a,stroke:#c62828
    style Reject3 fill:#ef9a9a,stroke:#c62828
```

---

## Key Data Structures

### ValidatorProof

```mermaid
classDiagram
    class ValidatorProof {
        bytes agentAddress
        bytes agentPubkey
        bytes quote
        bytes eventlog
    }

    class TEEQuote {
        string quote_type
        string measurement_register
        string device_id
        string compose_hash
        dict rtmrs
        dict td_report
        dict tcb_info
    }

    ValidatorProof --> TEEQuote : contains (as JSON bytes)
```

### Allowlist Mappings

```mermaid
graph TB
    subgraph "VerifiedIdentityRegistry Storage"
        VM[validatorAllowedAggregatedMrs<br/>mapping bytes32 => bool]
        VD[validatorAllowedDeviceIds<br/>mapping bytes32 => bool]
        AC[allowedAgentComposeHashes<br/>mapping bytes32 => bool]
        TA[trustlessAgents<br/>mapping address => bool]
    end

    style VM fill:#ffecb3,stroke:#f57c00
    style VD fill:#ffecb3,stroke:#f57c00
    style AC fill:#b2dfdb,stroke:#00695c
    style TA fill:#c5cae9,stroke:#283593,stroke-width:3px
```

---

## Usage Scenarios

### Scenario 1: Local Testing (Anvil)

```bash
# One-command demo
python tee_validation_demo.py run-all --network local
```

- Starts Anvil testnet automatically
- Uses deterministic test accounts
- Fast iteration for development

### Scenario 2: Customer Showcase (Multi-step on Base Sepolia)

```bash
# Step 1: Deploy infrastructure
python tee_validation_demo.py deploy --network base-sepolia

# Step 2: Register agents and configure allowlists
python tee_validation_demo.py setup-agents --network base-sepolia

# Step 3: Run live validation
python tee_validation_demo.py validate --network base-sepolia
```

- Separated steps for demonstration clarity
- Deployment state saved in `deployments/base-sepolia.json`
- Can run validation multiple times without redeployment

### Scenario 3: Multi-chain Deployment

Networks supported:
- `local` - Anvil testnet (Chain ID: 31337)
- `base-sepolia` - Base Sepolia testnet (Chain ID: 84532)
- `sepolia` - Ethereum Sepolia (Chain ID: 11155111)
- `optimism-sepolia` - Optimism Sepolia (Chain ID: 11155420)

---

## Security Guarantees

```mermaid
mindmap
    root((TEE Security))
        Validator Integrity
            Validator runs in TEE
            Quote proves TEE execution
            MR hash identifies code version
            Device ID proves hardware
        Agent Verification
            Client runs in TEE
            Compose hash proves container
            Device ID proves hardware
            Quote cannot be forged
        On-chain Trust
            Only validator can update status
            Allowlists prevent unauthorized TEE
            trustlessAgents mapping is immutable record
        Access Control
            Owner configures allowlists
            Validator authority via onlyValidator modifier
            Self-validation prevented
```

---

## Performance Characteristics

| Operation | Gas Cost (est.) | Notes |
|-----------|----------------|-------|
| Deploy IdentityRegistry | ~2,000,000 | One-time setup |
| Deploy VerifiedIdentityRegistry | ~3,000,000 | One-time setup |
| Register agent | ~150,000 | Per agent |
| Set validator proof | ~200,000 | One-time per validator |
| Configure allowlist | ~50,000 | Per allowlist entry |
| Update trustless status | ~100,000 | Per validation |
| Read trustless status | ~2,300 | View function (free) |

---

## Integration Points

```mermaid
graph TB
    subgraph "Python SDK"
        SDK[ChaosChainAgentSDK]
        TVA[TEEValidatorAgent]
        TCA[TEEClientAgent]
    end

    subgraph "dstack TEE"
        DSIM[dstack simulator]
        DPROD[dstack production]
    end

    subgraph "Smart Contracts"
        SC[ERC-8004 Contracts]
    end

    subgraph "Customer Integration"
        CA[Custom Agent Logic]
        CB[Custom Business Logic]
    end

    CA --> SDK
    CB --> TVA
    CB --> TCA
    SDK --> SC
    TVA --> DSIM
    TCA --> DSIM
    TVA --> SC

    style CA fill:#e1bee7,stroke:#6a1b9a,stroke-width:2px
    style CB fill:#e1bee7,stroke:#6a1b9a,stroke-width:2px
```

**Customer can extend:**
- Custom validation logic in `A2AVerificationService.verify_agent()`
- Additional allowlist checks
- Custom work report formats
- Integration with existing agent frameworks

---

## Deployment Configuration

Deployment state is saved per network in `deployments/{network}.json`:

```json
{
  "network": "base-sepolia",
  "chain_id": 84532,
  "rpc_url": "https://...",
  "contracts": {
    "identity_registry": "0x...",
    "reputation_registry": "0x...",
    "validation_registry": "0x...",
    "verified_identity_registry": "0x..."
  },
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
  "validator_proof": { "..." },
  "client_quote": { "..." },
  "validations": [
    {
      "timestamp": 1234567890,
      "report_id": "report_...",
      "status": "approved"
    }
  ]
}
```

This enables persistent multi-step demos and verification of historical validations.