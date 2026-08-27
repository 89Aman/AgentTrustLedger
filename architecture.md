# Agent Trust Ledger — Architecture Diagram
### Fortified Enterprise Fleet Track (All Things Agentic Hackathon)

```mermaid
graph TD
    subgraph Agent_Registry["[Capability 1] Agent Registry"]
        REG["Agent Registry Service (agents collection)"]
    end

    subgraph Agent_Identity["[Capability 4] Agent Identity"]
        BUYER["Buyer Agent (ADK)"]
        VENDOR["Vendor Agent (ADK)"]
        HMAC["HMAC-SHA256 Payload Signature & Verification"]
    end

    subgraph Agent_Gateway["[Capability 5] Agent Gateway"]
        PS1["Pub/Sub Topic: buyer-to-escrow"]
        PS2["Pub/Sub Topic: vendor-to-escrow"]
    end

    subgraph Agent_Runtime["[Capability 2] Agent Runtime"]
        CR["Cloud Run Escrow Mediator Service"]
        subgraph Security_Guard["[Capability 6] Security and Trust Guard"]
            CB["ADK before_model_callback (HMAC + Injection Screening)"]
        end
        ESCROW["Escrow Mediator Logic (Gemini 3.5)"]
    end

    subgraph Memory_Bank["[Capability 3] Memory Bank & Ledger"]
        FS1["Firestore: transactions (Escrow hold & audit subcollection)"]
        FS2["Firestore: reputation (Credit score & append-only audit ledger)"]
    end

    subgraph Agent_Observability["[Capability 7] Agent Observability"]
        OTEL["OpenTelemetry TracerProvider"]
        TRACE["Google Cloud Trace & Audit Logs"]
    end

    BUYER -->|1. Register Identity & Capabilities| REG
    VENDOR -->|1. Register Identity & Capabilities| REG
    BUYER -->|2. Sign Payload & Publish Txn Request| PS1
    PS1 -->|3. Route Message| CR
    CR -->|4. Inspect Signature & Prompt Patterns| CB
    CB -->|5. Verify Authorized Agent| REG
    CB -->|6. Hold Funds in Escrow| FS1
    VENDOR -->|7. Sign Delivery Claim & Publish| PS2
    PS2 -->|8. Route Claim| CR
    CR -->|9. Verify Delivery Evidence & Release Funds| FS1
    CR -->|10. Update Credit Score & Append Ledger| FS2
    CR -->|11. Emit Telemetry Spans| OTEL
    OTEL --> TRACE
```

## Capability Mapping Matrix

| Fortified Fleet Sub-Capability | Architectural Implementation | Verification / Demo Proof |
|---|---|---|
| **1. Agent Registry** | Firestore `agents` collection with status, capabilities, and key metadata | `registry/registry.py`, Step 1 in `scripts/run_demo.py` |
| **2. Agent Runtime** | Continuous serverless container on Cloud Run with async event handlers | Persistent Cloud Run endpoint, concurrent transaction processing |
| **3. Memory Bank** | Firestore `transactions` and `reputation` state stores with append-only ledger subcollections | `common/firestore_client.py`, Firestore console |
| **4. Agent Identity** | HMAC-SHA256 signed message payloads verified before any state mutation | `common/identity.py`, signature check in `security_guard.py` |
| **5. Agent Gateway** | Google Cloud Pub/Sub message broker enforcing topic access and routing | `common/pubsub.py`, Pub/Sub topics |
| **6. Security and Trust Guard** | Custom pre-model security layer (ADK `before_model_callback`) inspired by Model Armor principles. Validates HMAC signatures, detects prompt injection, and enforces state checks before LLM execution | `agents/escrow/security_guard.py`, Step 3 in `run_demo.py` |
| **7. Agent Observability** | OpenTelemetry spans attached to every lifecycle step and exported to Cloud Trace | `common/tracing.py`, Cloud Trace Console URL |
