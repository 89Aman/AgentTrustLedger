"""
Google Cloud Agent Registry integration module.

Read-only helpers for discovery and verification of officially registered
A2A agent services in Google Cloud Agent Registry.

Import-safe: does NOT make network or cloud calls at import time.
"""
import os
import json
import subprocess
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.error

from common.config import GOOGLE_CLOUD_PROJECT, AGENT_REGISTRY_LOCATION, CLOUD_RUN_SERVICE_URL
from common.agent_cards import get_card_endpoints

# Expected official service IDs and metadata
EXPECTED_AGENTS = {
    "escrow-mediator": {
        "display_name": "Agent Trust Ledger — Escrow Mediator",
        "card_path": "/.well-known/agent-card.json",
        "spec_file": "deployment/escrow-agent-card.json",
    },
    "buyer-agent": {
        "display_name": "Agent Trust Ledger — Buyer Agent",
        "card_path": "/agents/buyer/.well-known/agent-card.json",
        "spec_file": "deployment/buyer-agent-card.json",
    },
    "vendor-agent": {
        "display_name": "Agent Trust Ledger — Vendor Agent",
        "card_path": "/agents/vendor/.well-known/agent-card.json",
        "spec_file": "deployment/vendor-agent-card.json",
    },
}


def build_registry_metadata(base_url: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Build expected registration metadata for all 3 agents."""
    url = (base_url or CLOUD_RUN_SERVICE_URL or "").rstrip("/")
    entries = {}
    for agent_id, meta in EXPECTED_AGENTS.items():
        entries[agent_id] = {
            "id": agent_id,
            "display_name": meta["display_name"],
            "card_url": f"{url}{meta['card_path']}" if url else meta["card_path"],
            "spec_file": meta["spec_file"],
        }
    return entries


def validate_agent_card_urls(base_url: Optional[str] = None, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Validate that all 3 agent card discovery endpoints return HTTP 200 and valid JSON.
    Returns status map per endpoint.
    """
    url = (base_url or CLOUD_RUN_SERVICE_URL or "").rstrip("/")
    if not url:
        return {
            "all_valid": False,
            "error": "No base URL provided and CLOUD_RUN_SERVICE_URL is not set.",
            "endpoints": {}
        }

    results = {}
    all_valid = True

    for endpoint in get_card_endpoints():
        full_url = f"{url}{endpoint}"
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "AgentTrustLedger-Validator/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.getcode()
                content_type = resp.headers.get("Content-Type", "")
                body = resp.read().decode("utf-8")
                try:
                    data = json.loads(body)
                    is_json = isinstance(data, dict) and "name" in data
                except json.JSONDecodeError:
                    is_json = False

                valid = status_code == 200 and is_json
                results[endpoint] = {
                    "url": full_url,
                    "status_code": status_code,
                    "content_type": content_type,
                    "valid_json": is_json,
                    "valid": valid
                }
                if not valid:
                    all_valid = False
        except Exception as e:
            all_valid = False
            results[endpoint] = {
                "url": full_url,
                "error": str(e),
                "valid": False
            }

    return {
        "all_valid": all_valid,
        "base_url": url,
        "endpoints": results
    }


def _get_bearer_token() -> Optional[str]:
    """Obtain GCP bearer token via google-auth or gcloud CLI."""
    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        if creds.token:
            return creds.token
    except Exception:
        pass

    try:
        token = subprocess.check_output("gcloud auth print-access-token", shell=True, timeout=5).decode().strip()
        if token:
            return token
    except Exception:
        pass

    return None


def list_registered_services(
    project: Optional[str] = None,
    location: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List officially registered services from Google Cloud Agent Registry using REST API / gcloud CLI.
    """
    proj = project or GOOGLE_CLOUD_PROJECT
    loc = location or AGENT_REGISTRY_LOCATION

    # 1. REST API
    token = _get_bearer_token()
    if token:
        try:
            url = f"https://agentregistry.googleapis.com/v1/projects/{proj}/locations/{loc}/services"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("services", [])
        except Exception as e:
            print(f"[AgentRegistry] REST query failed: {e}")

    # 2. CLI Fallback
    commands = [
        ["gcloud", "alpha", "agent-registry", "services", "list", f"--project={proj}", f"--location={loc}", "--format=json"],
    ]

    for cmd in commands:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                try:
                    return json.loads(res.stdout)
                except json.JSONDecodeError:
                    pass
        except Exception:
            continue

    return []


def verify_official_registration(
    project: Optional[str] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify whether all 3 expected agents are officially registered in Google Cloud Agent Registry.
    Returns structured verification summary.
    """
    proj = project or GOOGLE_CLOUD_PROJECT
    loc = location or AGENT_REGISTRY_LOCATION

    services = list_registered_services(proj, loc)
    found_names = set()

    for s in services:
        name = s.get("name", "")
        # Name format: projects/.../locations/.../services/{service_id}
        service_id = name.split("/")[-1] if "/" in name else name
        found_names.add(service_id)

    status_per_agent = {}
    all_registered = True

    for expected_id, meta in EXPECTED_AGENTS.items():
        is_reg = expected_id in found_names
        status_per_agent[expected_id] = {
            "display_name": meta["display_name"],
            "registered": is_reg
        }
        if not is_reg:
            all_registered = False

    status_label = "Registered" if all_registered and len(services) >= 3 else ("Not registered" if len(services) == 0 else "Partially registered")

    return {
        "status": status_label,
        "all_registered": all_registered,
        "project": proj,
        "location": loc,
        "registered_count": len(found_names.intersection(set(EXPECTED_AGENTS.keys()))),
        "total_expected": len(EXPECTED_AGENTS),
        "agents": status_per_agent,
        "raw_services_count": len(services)
    }
