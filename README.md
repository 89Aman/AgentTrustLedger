# Agent Trust Ledger — "Credit Bureau for AI Agents"
### All Things Agentic Hackathon | Track: Fortified Enterprise Fleet

> **Live Cloud Run Deployment:** [https://agent-trust-ledger-1064660975371.us-central1.run.app](https://agent-trust-ledger-1064660975371.us-central1.run.app)
> **GCP Project:** `massive-house-506806-t6` (Region: `us-central1`)
> **Gemini Model:** `gemini-3.5-flash` via Vertex AI / Google ADK

As autonomous AI agents begin procuring, negotiating, and transacting with each other, there is no neutral **escrow and reputation layer** for agent-to-agent transactions.

The **Agent Trust Ledger** is an escrow mediator and credit bureau sitting between transacting AI agents. It holds funds in escrow, verifies identity and delivery conditions, enforces inline security guardrails, and maintains a public, auditable trust score.

---

## Fortified Enterprise Fleet Capabilities

| Capability | Technical Implementation |
|---|---|
| **Agent Registry** | Central catalog of enterprise-approved agents (`agents` Firestore collection) |
| **Agent Runtime** | Asynchronous escrow service deployed on Cloud Run |
| **Memory Bank** | Cross-session transaction escrow state and reputation ledger in Firestore |
| **Agent Identity** | HMAC-SHA256 signed message payloads verified before fund movement |
| **Agent Gateway** | Google Cloud Pub/Sub enforcing routing and message policies |
| **Security and Trust Guard** | Custom ADK `before_model_callback` intercepting spoofed claims and prompt injection before LLM execution |
| **Agent Observability** | OpenTelemetry tracing exported directly to Google Cloud Trace |

---
## Security & Architecture Caveats (Demo vs. Production)

1. **Security and Trust Guard vs. Google Model Armor**:
   The Security and Trust Guard is a custom pre-model security layer inspired by Model Armor principles. It validates HMAC signatures, detects prompt-injection patterns, and enforces transaction-state checks before the LLM processes claims. This is not the official Google Model Armor service, but demonstrates the same architectural pattern of intercepting unsafe inputs before model execution.

2. **Agent Identity**:
   This project uses HMAC-SHA256 with a shared secret key for agent message signing. For hackathon demonstration purposes, this proves the architectural pattern of **Agent Identity** and **Security Guardrails**. In a production system, shared-secret HMAC would be replaced by asymmetric key pairs (e.g. Ed25519) per agent or Google Cloud IAM service account credentials.

In a full enterprise production system:
1. Shared-secret HMAC would be replaced by asymmetric key pairs (e.g. Ed25519) per agent or Google Cloud IAM service account credentials.
2. Escrow balances would integrate with real digital payment processors or smart contracts.

---

## Pre-Existing Code & Template Disclosure
Built newly during the hackathon period using official Google Cloud Python SDKs (`google-genai`, `google-cloud-pubsub`, `google-cloud-firestore`), OpenTelemetry SDKs, and Flask. No pre-existing proprietary codebase or third-party template was used.

---

## License
Apache 2.0
