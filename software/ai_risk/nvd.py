from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _impact_to_score(value: str | None) -> float:
    mapping = {
        "NONE": 0.0,
        "LOW": 0.5,
        "HIGH": 1.0,
    }
    return mapping.get(str(value or "").upper(), 0.0)


def _extract_metrics(vulnerability: dict) -> dict[str, float | str]:
    cve = vulnerability.get("cve", {})
    metrics = cve.get("metrics", {})
    preferred_keys = ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]
    metric_entry = None
    for key in preferred_keys:
        entries = metrics.get(key, [])
        if entries:
            metric_entry = entries[0]
            break
    if metric_entry is None:
        return {
            "cvss_exploitability": 0.0,
            "cvss_c": 0.0,
            "cvss_i": 0.0,
            "cvss_a": 0.0,
            "cvss_base_score": 0.0,
            "cvss_source": "",
        }
    cvss_data = metric_entry.get("cvssData", {})
    return {
        "cvss_exploitability": float(metric_entry.get("exploitabilityScore", cvss_data.get("baseScore", 0.0))),
        "cvss_c": _impact_to_score(cvss_data.get("confidentialityImpact")),
        "cvss_i": _impact_to_score(cvss_data.get("integrityImpact")),
        "cvss_a": _impact_to_score(cvss_data.get("availabilityImpact")),
        "cvss_base_score": float(cvss_data.get("baseScore", 0.0)),
        "cvss_source": str(metric_entry.get("source", "")),
    }


def fetch_cve_details(cve_id: str, api_key: str | None = None) -> dict[str, float | str]:
    query = urlencode({"cveId": cve_id})
    url = f"{NVD_API_BASE}?{query}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if api_key:
        headers["apiKey"] = api_key
    request = Request(url, headers=headers)
    with urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    vulnerabilities = payload.get("vulnerabilities", [])
    if not vulnerabilities:
        return {
            "cvss_exploitability": 0.0,
            "cvss_c": 0.0,
            "cvss_i": 0.0,
            "cvss_a": 0.0,
            "cvss_base_score": 0.0,
            "cvss_source": "",
        }
    return _extract_metrics(vulnerabilities[0])


def enrich_cves_with_cache(cve_ids: list[str], cache_path: str | Path, api_key: str | None = None, min_interval_s: float = 0.7) -> dict[str, dict[str, float | str]]:
    cache_path = Path(cache_path)
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        cache = {}
    updated = False
    for cve_id in sorted({cve_id for cve_id in cve_ids if cve_id and cve_id.upper().startswith("CVE-")}):
        if cve_id in cache:
            continue
        cache[cve_id] = fetch_cve_details(cve_id, api_key=api_key)
        updated = True
        time.sleep(min_interval_s)
    if updated:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    return cache
