# Agent Trust Ledger — Autonomous AI Agent Escrow & Reputation Rail
### Google Cloud Agentic AI Hackathon | Track: Fortified Enterprise Fleet

> **Deployed Cloud Run Service:** [https://agent-trust-ledger-1064660975371.us-central1.run.app](https://agent-trust-ledger-1064660975371.us-central1.run.app)  
> **Google Cloud Project ID:** `massive-house-506806-t6` (Region: `us-central1`)  
> **Gemini Engine:** Vertex AI via Google ADK (`gemini-3.5-flash`)  
> **Official A2A Agent Cards:** [Escrow Mediator](https://agent-trust-ledger-1064660975371.us-central1.run.app/.well-known/agent-card.json) | [Buyer Agent](https://agent-trust-ledger-1064660975371.us-central1.run.app/agents/buyer/.well-known/agent-card.json) | [Vendor Agent](https://agent-trust-ledger-1064660975371.us-central1.run.app/agents/vendor/.well-known/agent-card.json)

---

## 1. Architecture Overview & The Two Registry Layers

As autonomous AI agents procure, negotiate, and transact with one another, they require both an **operational transaction mediator** and an **enterprise discovery catalog**.

The Agent Trust Ledger implements two distinct registry layers:

1. **Application Agent Registry (Firestore):**
   - Operational runtime database storing agent identity, policy constraints (spend limits, approval thresholds), dynamic status (`active`, `paused`, `suspended`), and cross-session reputation records.
   - Manages stateful memory banks, append-only audit ledgers, and transaction holds.

2. **Google Cloud Agent Registry:**
   - Centralized official discovery and governance catalog within Google Cloud.
   - Indexes the three deployed A2A Agent Cards via declared `Service` resources for cross-organization agent discovery.

---

## 2. A2A Discovery Endpoints

The deployed Cloud Run service hosts three public Agent-to-Agent (A2A) discovery endpoints:

| Agent Role | Discovery Endpoint | Official Service ID |
|---|---|---|
| **Escrow Mediator** | `/.well-known/agent-card.json` | `escrow-mediator` |
| **Buyer Agent** | `/agents/buyer/.well-known/agent-card.json` | `buyer-agent` |
| **Vendor Agent** | `/agents/vendor/.well-known/agent-card.json` | `vendor-agent` |

---

## 3. Reproducible Testing Instructions

Judges and reviewers can reproduce and verify all capabilities in **under 60 seconds** without needing Google Cloud credentials or billing. The entire suite runs fully offline using deterministic in-memory mock fallbacks.

### A. Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/89Aman/AgentTrustLedger.git
cd AgentTrustLedger

# 2. Create and activate a virtual environment (optional but recommended)
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### B. Run Automated Test Suite (43 Tests)

Run the full automated test suite using either `pytest` or Python's built-in `unittest`:

```bash
# Option 1: pytest (verbose output)
pytest -v

# Option 2: unittest (zero third-party test runners needed)
python -m unittest discover tests -v
```

**Expected Result:**
```text
Ran 43 tests in 0.45s
OK (43 passed)
```

#### Test Suite Capability Coverage Matrix

| Test Module | Tests | Fortified Fleet Capability Verified |
|---|:---:|---|
| `tests/test_agent_cards.py` | 13 | **Agent Registry**: Validates A2A Agent Card specs, JSON schema adherence, schema versions, and endpoints for all 3 agents. |
| `tests/test_security_guard.py` | 6 | **Security & Trust Guard**: Verifies cryptographic HMAC validation, blocks spoofed payloads, and detects prompt-injection patterns. |
| `tests/test_governance.py` | 5 | **Autonomy Governance**: Tests `autonomous`, `guarded_auto`, and `manual` policy modes, threshold enforcement, and operator status updates. |
| `tests/test_agents.py` | 2 | **Agent Runtime & Gateway**: Validates multi-agent transaction orchestration, fund escrowing, and delivery verification across Pub/Sub. |
| `tests/test_registry.py` | 4 | **Application Registry**: Tests agent registration, status management (`active`, `paused`, `suspended`), and authorization checks. |
| `tests/test_identity.py` | 3 | **Agent Identity**: Tests cryptographic HMAC-SHA256 signature generation and tamper detection. |
| `tests/test_config.py` | 10 | **System Configuration**: Tests environment variable parsing, safe defaults, and cloud vs. fallback switching. |

---

### C. Live Cloud Run Deployment Verification

You can directly verify the live production service deployed on Google Cloud without cloning the repository:

```bash
# 1. Verify Escrow Mediator A2A Agent Card
curl -s https://agent-trust-ledger-1064660975371.us-central1.run.app/.well-known/agent-card.json

# 2. Verify Buyer Agent A2A Card
curl -s https://agent-trust-ledger-1064660975371.us-central1.run.app/agents/buyer/.well-known/agent-card.json

# 3. Verify Vendor Agent A2A Card
curl -s https://agent-trust-ledger-1064660975371.us-central1.run.app/agents/vendor/.well-known/agent-card.json

# 4. Verify Live System State & Telemetry
curl -s https://agent-trust-ledger-1064660975371.us-central1.run.app/api/state
```

---

### D. Local Interactive Dashboard Verification

```bash
# Start the local development server
python dashboard/app.py
```

1. Open `http://localhost:8080` in your web browser.
2. Click **"Initiate Escrow ($5,000)"** → Observe funds locked in escrow and an audit log appended to the memory bank.
3. Click **"Test Spoofed Claim"** → Observe the **Security & Trust Guard** intercept and block the spoofed signature, raising a security incident.
4. Click **"Submit Legit Claim"** → Observe evidence verification against contract conditions and release of funds.

---

## 4. Google Cloud Deployment (Windows PowerShell)

### Step 1 — Authenticate, Set Project & Install Alpha Component

```powershell
gcloud auth login
gcloud config set project massive-house-506806-t6

# Install Agent Registry alpha CLI component (Run PowerShell as Admin if needed)
gcloud components update
gcloud components install alpha
gcloud alpha agent-registry services create --help
```

### Step 2 — Enable Required GCP APIs

```powershell
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudtrace.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable agentregistry.googleapis.com
```

### Step 3 — Deploy to Cloud Run

```powershell
.\scripts\deploy.ps1
```

The script builds the container with `gunicorn`, deploys to `us-central1`, retrieves the live URL, and validates all three agent-card endpoints.

### Step 4 — Export Local Agent Cards

```powershell
$env:CLOUD_RUN_SERVICE_URL = "https://agent-trust-ledger-1064660975371.us-central1.run.app"
python scripts/export_agent_cards.py --base-url $env:CLOUD_RUN_SERVICE_URL
```

This generates `deployment/escrow-agent-card.json`, `deployment/buyer-agent-card.json`, and `deployment/vendor-agent-card.json` containing the active service base URL.

### Step 5 — Register Agents in Google Cloud Agent Registry

```powershell
$env:GOOGLE_CLOUD_PROJECT = "massive-house-506806-t6"
$env:AGENT_REGISTRY_LOCATION = "us-central1"
.\scripts\register_agents.ps1
```

This runs the official Service creation commands:
```powershell
gcloud alpha agent-registry services create escrow-mediator `
  --project=massive-house-506806-t6 `
  --location=us-central1 `
  --display-name="Agent Trust Ledger — Escrow Mediator" `
  --agent-spec-type=a2a-agent-card `
  --agent-spec-content="deployment/escrow-agent-card.json"
```

Service verification:
```powershell
# List registered services
gcloud alpha agent-registry services list `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --location=$env:AGENT_REGISTRY_LOCATION

# List registered agents
gcloud alpha agent-registry agents list `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --location=$env:AGENT_REGISTRY_LOCATION

# Describe service
gcloud alpha agent-registry services describe escrow-mediator `
  --project=$env:GOOGLE_CLOUD_PROJECT `
  --location=$env:AGENT_REGISTRY_LOCATION
```

### Step 6 — Verify Deployment & Discovery

```powershell
.\scripts\verify_deployment.ps1 -ServiceUrl $env:CLOUD_RUN_SERVICE_URL
```

---

## 5. Configuration Reference

| Variable | Description | Default / Example |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID | `massive-house-506806-t6` |
| `GOOGLE_CLOUD_LOCATION` | Primary GCP Region | `us-central1` |
| `AGENT_REGISTRY_LOCATION` | Agent Registry Region | `us-central1` |
| `GEMINI_MODEL` | Vertex AI Gemini model name | `gemini-3.5-flash` |
| `CLOUD_RUN_SERVICE_URL` | Deployed Cloud Run base URL | `https://agent-trust-ledger-xxx.run.app` |
| `USE_FIRESTORE` | Enable production Firestore backend | `true` (deployed) / `false` (local) |
| `USE_PUBSUB` | Enable production Google Cloud Pub/Sub | `true` (deployed) / `false` (local) |
| `USE_CLOUD_TRACE` | Enable OpenTelemetry Cloud Trace export | `true` (deployed) / `false` (local) |
| `DEMO_MODE` | Allow interactive dashboard actions | `true` |
| `PORT` | Web server listening port | `8080` |

---

## 6. Required IAM Roles & Permissions

### Developer / Deployer Account
- `roles/run.admin` — Deploy Cloud Run service
- `roles/iam.serviceAccountUser` — Attach service account to Cloud Run
- `roles/serviceusage.serviceUsageAdmin` — Enable required APIs
- `roles/agentregistry.admin` — Register and manage Agent Registry service entries

### Cloud Run Runtime Service Account
- `roles/datastore.user` — Read and write Firestore operational collections
- `roles/pubsub.publisher` — Publish inter-agent event messages
- `roles/pubsub.subscriber` — Pull / receive pushed event messages
- `roles/cloudtrace.agent` — Export OpenTelemetry spans to Google Cloud Trace
- `roles/aiplatform.user` — Invoke Vertex AI Gemini models

---

## 7. Important Product & Security Disclosures

1. **Simulated Escrow Funds / Demo Credits:**
   All funds handled by this application are simulated balances (demo credits). No real currency or payment processing is executed.

2. **Security & Trust Guard:**
   `Security & Trust Guard — custom pre-model security validation inspired by Model Armor principles.`
   It runs deterministic HMAC signature verification, agent authorization checks, and prompt-injection pattern screening before any claim payload is evaluated by an LLM.

3. **Agent Identity:**
   Demonstration mode uses HMAC-SHA256 with key verification to demonstrate the cryptographic identity pattern. In enterprise production, this would be replaced with asymmetric Ed25519 key pairs per agent or Google Cloud Workload Identity Federation.

---

## 8. Troubleshooting

- **Agent Card returns 404:** Verify `CLOUD_RUN_SERVICE_URL` matches the deployed URL and routes in `dashboard/app.py` are active.
- **Agent Registry API disabled:** Run `gcloud services enable agentregistry.googleapis.com --project=massive-house-506806-t6`.
- **Missing IAM permissions:** Ensure your user has `roles/agentregistry.admin` and `roles/run.admin`.
- **gcloud CLI command group:** If `gcloud alpha agent-registry` is not recognized, run `gcloud components update` and `gcloud components install alpha` in an Administrator PowerShell session.
- **Firestore / Pub/Sub fallback:** App logs `[FirestoreClient] Initialized: in-memory fallback mode` when running without GCP credentials. When deployed, set `USE_FIRESTORE=true` and `USE_PUBSUB=true`.
