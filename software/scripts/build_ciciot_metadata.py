from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_risk.demo_data import CVE_PROFILES
from ai_risk.utils.io import write_rows


FAMILY_KEY_MAP = {
    "Benign": "benign",
    "DDoS": "ddos",
    "DoS": "dos",
    "Recon": "recon",
    "Web": "web",
    "BruteForce": "bruteforce",
    "Spoofing": "spoofing",
    "Mirai": "mirai",
}

SECTION_NORMALIZATION = {
    "dos": "DoS",
    "webbased": "Web",
    "mirai": "Mirai",
    "ddos": "DDoS",
    "spoofing": "Spoofing",
    "recon": "Recon",
    "bruteforce": "BruteForce",
}

ATTACK_DISPLAY_BY_FAMILY = {
    "DoS": {
        "httpflood": "DoS-HTTP_Flood",
        "synflood": "DoS-SYN_Flood",
        "tcpflood": "DoS-TCP_Flood",
        "udpflood": "DoS-UDP_Flood",
    },
    "Web": {
        "backdoormalware": "Backdoor_Malware",
        "browserhijacking": "BrowserHijacking",
        "commandinjection": "CommandInjection",
        "sqlinjection": "SqlInjection",
        "uploadingattack": "Uploading_Attack",
        "xss": "XSS",
    },
    "Mirai": {
        "greeth": "Mirai-greeth_flood",
        "greip": "Mirai-greip_flood",
        "udpplain": "Mirai-udpplain",
    },
    "DDoS": {
        "ackfragmentation": "DDoS-ACK_Fragmentation",
        "httpflood": "DDoS-HTTP_Flood",
        "icmpflood": "DDoS-ICMP_Flood",
        "icmpfragmentation": "DDoS-ICMP_Fragmentation",
        "pshackflood": "DDoS-PSHACK_Flood",
        "rstfinflood": "DDoS-RSTFINFlood",
        "slowloris": "DDoS-SlowLoris",
        "synflood": "DDoS-SYN_Flood",
        "synonymousipflood": "DDoS-SynonymousIP_Flood",
        "tcpflood": "DDoS-TCP_Flood",
        "udpflood": "DDoS-UDP_Flood",
        "udpfragmentation": "DDoS-UDP_Fragmentation",
    },
    "Spoofing": {
        "dnsspoofing": "DNS_Spoofing",
        "arpspoofing": "MITM-ArpSpoofing",
    },
    "Recon": {
        "hostdiscovery": "Recon-HostDiscovery",
        "osscan": "Recon-OSScan",
        "pingsweep": "Recon-PingSweep",
        "portscan": "Recon-PortScan",
        "vulnerabilityscan": "VulnerabilityScan",
    },
    "BruteForce": {
        "dictionarybruteforce": "DictionaryBruteForce",
    },
}

IGNORED_VICTIM_LINES = {
    "",
    "iotattacksvictims",
    "attackstargetdevices",
    "attacktargetdevice",
    "attacks target devices",
    "attack target device",
    "whole network",
}


def normalize_token(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "", value or "").strip().lower()
    return value


def normalize_event_type(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build official CICIoT metadata artifacts from the bundled notebook and victim PDF.")
    parser.add_argument("--target", default=str(ROOT / "data"), help="Target data directory.")
    parser.add_argument(
        "--raw-root",
        default=str(ROOT / "data" / "raw" / "ciciot2023"),
        help="Location of the downloaded official CICIoT2023 bundles.",
    )
    return parser.parse_args()


def load_notebook_text(ipynb_path: Path) -> str:
    notebook = json.loads(ipynb_path.read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))


def build_taxonomy_rows(notebook_text: str) -> list[dict[str, object]]:
    family_pairs = re.findall(r"dict_7classes\['([^']+)'\]\s*=\s*'([^']+)'", notebook_text)
    binary_pairs = dict(re.findall(r"dict_2classes\['([^']+)'\]\s*=\s*'([^']+)'", notebook_text))
    rows: list[dict[str, object]] = []
    for event_label, family_7class in sorted(family_pairs):
        event_type = normalize_event_type(event_label)
        family_key = FAMILY_KEY_MAP[family_7class]
        binary_label = binary_pairs.get(event_label, "Attack")
        rows.append(
            {
                "event_type": event_type,
                "event_label": event_label,
                "family_7class": family_7class,
                "family_key": family_key,
                "binary_label": binary_label,
                "is_attack": int(binary_label != "Benign"),
                "taxonomy_source": "official_example_notebook",
            }
        )
    return rows


def iter_pdf_lines(pdf_path: Path) -> Iterable[str]:
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split()).strip()
            if line:
                yield line


def build_victim_rows(pdf_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_family: str | None = None
    current_attack: str | None = None
    for line in iter_pdf_lines(pdf_path):
        normalized = normalize_token(line)
        if normalized.isdigit():
            continue
        if normalized in SECTION_NORMALIZATION:
            current_family = SECTION_NORMALIZATION[normalized]
            current_attack = None
            continue
        if normalized in {"ciciot2023arealtimedatasetandbenchmarkforlargescaleattacksiniotenvironment", "iotattacksvictims"}:
            continue
        if normalized in {"euclidescarlospintonetosajjaddadkhahraphaelferreiraalirezazohourianrongxinglualiaaghorbani"}:
            continue
        if current_family and normalized in ATTACK_DISPLAY_BY_FAMILY[current_family]:
            current_attack = ATTACK_DISPLAY_BY_FAMILY[current_family][normalized]
            continue
        if not current_family or not current_attack:
            continue
        if normalized in IGNORED_VICTIM_LINES:
            continue
        rows.append(
            {
                "event_type": normalize_event_type(current_attack),
                "event_label": current_attack,
                "family_7class": current_family,
                "victim_device": line,
                "victim_source": "official_victims_pdf",
            }
        )
    return rows


def build_cve_rows(taxonomy_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in taxonomy_rows:
        family_key = str(row["family_key"])
        profile = CVE_PROFILES[family_key]
        rows.append(
            {
                "event_type": row["event_type"],
                "event_label": row["event_label"],
                "family_7class": row["family_7class"],
                "family_key": family_key,
                "cve_id": profile.cve_id,
                "cvss_exploitability": profile.exploitability,
                "cvss_c": profile.impact_c,
                "cvss_i": profile.impact_i,
                "cvss_a": profile.impact_a,
                "mapping_source": "official_taxonomy_plus_family_surrogate",
                "mapping_note": "Explicit attack-to-family map comes from the official CICIoT example notebook; CVE values remain representative family-level surrogates until a device-level curated map is supplied.",
            }
        )
    return rows


def build_surrogate_nvd_cache(cve_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    cache: dict[str, dict[str, object]] = {}
    for row in cve_rows:
        cve_id = str(row["cve_id"])
        if cve_id in cache:
            continue
        cache[cve_id] = {
            "cvss_exploitability": float(row["cvss_exploitability"]),
            "cvss_c": float(row["cvss_c"]),
            "cvss_i": float(row["cvss_i"]),
            "cvss_a": float(row["cvss_a"]),
            "cvss_base_score": 0.0,
            "cvss_source": "official_taxonomy_plus_family_surrogate",
        }
    return cache


def main() -> None:
    args = parse_args()
    target_dir = Path(args.target).resolve()
    raw_root = Path(args.raw_root).resolve()
    example_ipynb = raw_root / "example" / "example.ipynb"
    victims_pdf = raw_root / "Supplementary Materials" / "README_Victims_List.pdf"
    if not example_ipynb.exists():
        raise FileNotFoundError(f"Official example notebook not found: {example_ipynb}")
    if not victims_pdf.exists():
        raise FileNotFoundError(f"Official victims PDF not found: {victims_pdf}")

    taxonomy_rows = build_taxonomy_rows(load_notebook_text(example_ipynb))
    victim_rows = build_victim_rows(victims_pdf)
    cve_rows = build_cve_rows(taxonomy_rows)

    taxonomy_path = write_rows(
        target_dir / "attack_taxonomy.csv",
        taxonomy_rows,
        ["event_type", "event_label", "family_7class", "family_key", "binary_label", "is_attack", "taxonomy_source"],
    )
    victims_path = write_rows(
        target_dir / "attack_victims.csv",
        victim_rows,
        ["event_type", "event_label", "family_7class", "victim_device", "victim_source"],
    )
    cve_path = write_rows(
        target_dir / "cve_map.csv",
        cve_rows,
        [
            "event_type",
            "event_label",
            "family_7class",
            "family_key",
            "cve_id",
            "cvss_exploitability",
            "cvss_c",
            "cvss_i",
            "cvss_a",
            "mapping_source",
            "mapping_note",
        ],
    )
    nvd_cache_path = target_dir / "nvd_cache.json"
    nvd_cache_path.write_text(json.dumps(build_surrogate_nvd_cache(cve_rows), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"taxonomy rows: {len(taxonomy_rows)} -> {taxonomy_path}")
    print(f"victim rows: {len(victim_rows)} -> {victims_path}")
    print(f"cve rows: {len(cve_rows)} -> {cve_path}")
    print(f"surrogate cache entries: {len(build_surrogate_nvd_cache(cve_rows))} -> {nvd_cache_path}")


if __name__ == "__main__":
    main()
