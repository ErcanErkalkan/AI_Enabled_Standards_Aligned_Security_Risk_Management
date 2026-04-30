from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CVEProfile:
    cve_id: str
    exploitability: float
    impact_c: float
    impact_i: float
    impact_a: float
    severity_shift: float


CVE_PROFILES: dict[str, CVEProfile] = {
    "benign": CVEProfile("CVE-0000-0000", 0.05, 0.05, 0.05, 0.05, 0.00),
    "ddos": CVEProfile("CVE-2024-1101", 0.82, 0.32, 0.18, 0.92, 1.45),
    "dos": CVEProfile("CVE-2024-1102", 0.74, 0.28, 0.20, 0.86, 1.20),
    "recon": CVEProfile("CVE-2024-1103", 0.48, 0.10, 0.12, 0.20, 0.55),
    "web": CVEProfile("CVE-2024-1104", 0.77, 0.71, 0.69, 0.40, 1.00),
    "bruteforce": CVEProfile("CVE-2024-1105", 0.58, 0.34, 0.37, 0.12, 0.68),
    "spoofing": CVEProfile("CVE-2024-1106", 0.53, 0.41, 0.46, 0.14, 0.72),
    "mirai": CVEProfile("CVE-2024-1107", 0.88, 0.40, 0.36, 0.95, 1.62),
}


def generate_demo_dataframe(
    seed: int,
    n_assets: int = 24,
    steps_per_asset: int = 280,
    attack_burst_prob: float = 0.08,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = np.datetime64("2025-01-01T00:00")
    all_rows: list[dict[str, object]] = []
    event_types = ["ddos", "dos", "recon", "web", "bruteforce", "spoofing", "mirai"]

    for asset_index in range(n_assets):
        asset_id = f"asset_{asset_index:03d}"
        asset_value_raw = float(rng.uniform(50_000, 500_000))
        hf_base = float(np.clip(rng.beta(2.4, 6.0), 0.02, 0.75))
        device_risk = float(rng.uniform(0.1, 0.9))
        current_attack = None
        burst_remaining = 0

        for step in range(steps_per_asset):
            timestamp = start + np.timedelta64(asset_index * 5 + step * 10, "m")
            if burst_remaining <= 0 and rng.random() < attack_burst_prob:
                current_attack = str(rng.choice(event_types))
                burst_remaining = int(rng.integers(4, 10))
            label = int(burst_remaining > 0)
            event_type = current_attack if label else "benign"
            if burst_remaining > 0:
                burst_remaining -= 1
            if burst_remaining <= 0:
                current_attack = None

            profile = CVE_PROFILES[event_type]
            temporal_wave = 0.3 * np.sin(step / 18.0) + 0.15 * np.cos(step / 11.0)
            normal_noise = rng.normal(0.0, 0.25, size=8)
            rate_base = 1.2 + device_risk + temporal_wave
            attack_shift = profile.severity_shift if label else 0.0
            syn_boost = 0.45 if event_type in {"ddos", "dos", "mirai"} else 0.05
            http_boost = 0.55 if event_type in {"web", "dos"} else 0.02
            dns_boost = 0.45 if event_type == "spoofing" else 0.01

            packet_rate = max(0.0, 85 + 45 * rate_base + 120 * attack_shift + normal_noise[0] * 20)
            byte_rate = max(0.0, 900 + 380 * rate_base + 1500 * attack_shift + normal_noise[1] * 120)
            duration = max(0.0, 6 + 4 * (1.0 - label) + normal_noise[2] * 2)
            syn_flag = float(np.clip(0.10 + syn_boost + 0.1 * normal_noise[3], 0.0, 1.0))
            ack_flag = float(np.clip(0.35 - 0.14 * label + 0.1 * normal_noise[4], 0.0, 1.0))
            rst_flag = float(np.clip(0.05 + 0.15 * label + 0.08 * normal_noise[5], 0.0, 1.0))
            http = float(np.clip(0.08 + http_boost + 0.1 * normal_noise[6], 0.0, 1.0))
            dns = float(np.clip(0.03 + dns_boost + 0.08 * normal_noise[7], 0.0, 1.0))
            tcp = float(np.clip(0.70 + 0.10 * label + rng.normal(0.0, 0.05), 0.0, 1.0))
            udp = float(np.clip(0.18 + (0.20 if event_type in {"ddos", "mirai"} else 0.02) + rng.normal(0.0, 0.04), 0.0, 1.0))
            icmp = float(np.clip(0.04 + (0.18 if event_type == "recon" else 0.01) + rng.normal(0.0, 0.03), 0.0, 1.0))
            unusual_peer_ratio = float(np.clip(0.10 + 0.40 * label + rng.normal(0.0, 0.08), 0.0, 1.0))
            failed_logins = float(max(0.0, rng.poisson(0.2 + (2.8 if event_type == "bruteforce" else 0.1))))
            port_entropy = float(np.clip(0.18 + 0.50 * label + rng.normal(0.0, 0.08), 0.0, 1.0))
            device_entropy = float(np.clip(0.15 + 0.38 * label + rng.normal(0.0, 0.10), 0.0, 1.0))
            hf_failure_ratio = float(np.clip(hf_base + 0.08 * label + rng.normal(0.0, 0.03), 0.0, 1.0))
            hf_policy_violations = float(np.clip(hf_base * 0.7 + 0.06 * label + rng.normal(0.0, 0.03), 0.0, 1.0))
            hf_training_gap = float(np.clip(hf_base * 0.8 + 0.04 * label + rng.normal(0.0, 0.03), 0.0, 1.0))

            all_rows.append(
                {
                    "timestamp": pd.Timestamp(timestamp.astype("datetime64[ns]")),
                    "asset_id": asset_id,
                    "label": label,
                    "event_type": event_type,
                    "cve_id": profile.cve_id,
                    "asset_value_raw": asset_value_raw,
                    "flow_duration": duration,
                    "packet_rate": packet_rate,
                    "byte_rate": byte_rate,
                    "syn_flag_number": syn_flag,
                    "ack_flag_number": ack_flag,
                    "rst_flag_number": rst_flag,
                    "http": http,
                    "dns": dns,
                    "tcp": tcp,
                    "udp": udp,
                    "icmp": icmp,
                    "failed_logins": failed_logins,
                    "port_entropy": port_entropy,
                    "device_entropy": device_entropy,
                    "unusual_peer_ratio": unusual_peer_ratio,
                    "cvss_exploitability": profile.exploitability,
                    "cvss_c": profile.impact_c,
                    "cvss_i": profile.impact_i,
                    "cvss_a": profile.impact_a,
                    "hf_failure_ratio": hf_failure_ratio,
                    "hf_policy_violations": hf_policy_violations,
                    "hf_training_gap": hf_training_gap,
                }
            )
    frame = pd.DataFrame(all_rows).sort_values(["timestamp", "asset_id"]).reset_index(drop=True)
    return frame

