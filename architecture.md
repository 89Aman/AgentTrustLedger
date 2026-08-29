# Agent Trust Ledger — Architecture Diagram
### Fortified Enterprise Fleet Track (All Things Agentic Hackathon)

```mermaid
graph TD
    subgraph Discovery_Layer["Official Governance & Discovery Layer"]
        AR["Google Cloud Agent Registry (Service Resources)"]
        CARD_ESCROW["/.well-known/agent-card.json"]
        CARD_BUYER["/agents/buyer/.well-known/agent-card.json"]
        CARD_VENDOR["/agents/vendor/.well-known/agent-card.json"]
        CARD_ESCROW -->|Indexes A2A Spec| AR
        CARD_BUYER -->|Indexes A2A Spec| AR
        CARD_VENDOR -->|Indexes A2A Spec| AR
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
        subgraph Security_Guard["[Capability 6] Security & Trust Guard"]
            CB["Pre-Model Validation (HMAC + Injection Screening)"]
        end
        ESCROW["Escrow Mediator Logic (Gemini via ADK)"]
    end

    subgraph Operational_Registry["[Capability 1] Application Agent Registry & Memory Bank"]
        REG["Firestore: agents (Operational Status & Spend Policies)"]
        FS1["Firestore: transactions (Simulated Escrow Holds & Audit Log)"]
        FS2["Firestore: reputation (Credit Scores & Append-Only Ledger)"]
        FS3["Firestore: audit_events (Global Incident & Verification Stream)"]
    end

    subgraph Agent_Observability["[Capability 7] Agent Observability"]
        OTEL["OpenTelemetry TracerProvider"]
        TRACE["Google Cloud Trace & Cloud Logging"]
    end

    BUYER -->|1. Sign Request & Publish| PS1
    PS1 -->|2. Route Message| CR
    CR -->|3. Inspect Signature & Injections| CB
    CB -->|4. Verify Agent Authorized & Status| REG
    CB -->|5. Hold Simulated Credits in Escrow| FS1
    VENDOR -->|6. Sign Delivery Claim & Publish| PS2
    PS2 -->|7. Route Claim| CR
    CR -->|8. Verify Delivery Evidence & Release Demo Credits| FS1
    CR -->|9. Update Credit Score & Append Ledger| FS2
    CR -->|10. Persist Audit Record| FS3
    CR -->|11. Emit Telemetry Spans| OTEL
    OTEL --> TRACE
```

---

## Fortified Fleet Sub-Capability Mapping Matrix

| Fortified Fleet Sub-Capability | Architectural Implementation | Verification / Demo Proof |
|---|---|---|
| **1. Agent Registry** | **Layer A:** Official Google Cloud Agent Registry indexing 3 A2A cards.<br/>**Layer B:** Application Agent Registry in Firestore for operational runtime status & policies. | `scripts/register_agents.ps1`, `/.well-known/agent-card.json`, Firestore `agents` collection |
| **2. Agent Runtime** | Continuous containerized escrow service on Google Cloud Run with async event handlers. | Persistent Cloud Run endpoint, concurrent transaction processing |
| **3. Memory Bank** | Firestore `transactions`, `reputation`, and `audit_events` state stores with append-only ledger subcollections. | `common/firestore_client.py`, Firestore Console |
| **4. Agent Identity** | HMAC-SHA256 signed message payloads verified before any state mutation or fund movement. | `common/identity.py`, signature check in `security_guard.py` |
| **5. Agent Gateway** | Google Cloud Pub/Sub message broker enforcing topic access and routing (`buyer-to-escrow`, `vendor-to-escrow`). | `common/pubsub.py`, Pub/Sub Console |
| **6. Security & Trust Guard** | Custom pre-model security validation inspired by Model Armor principles. Validates HMAC signatures, detects prompt injection, and enforces state checks before LLM execution. | `agents/escrow/security_guard.py`, spoof test in `tests/test_security_guard.py` |
| **7. Agent Observability** | OpenTelemetry spans attached to every lifecycle step and exported to Google Cloud Trace. | `common/tracing.py`, Google Cloud Trace Console |
