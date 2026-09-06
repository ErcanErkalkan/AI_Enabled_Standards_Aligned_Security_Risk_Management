from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "software" / "r1_payload" / "manifest.json"


def _decode_entry(entry: dict) -> bytes:
    encoded = "".join(
        (REPO_ROOT / part).read_text(encoding="ascii").strip()
        for part in entry["payload_parts"]
    )
    return gzip.decompress(base64.b64decode(encoded))


def main() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in entries:
        data = _decode_entry(entry)
        if len(data) != entry["bytes"]:
            raise SystemExit(
                f"payload size mismatch for {entry['target']}: {len(data)} != {entry['bytes']}"
            )
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            raise SystemExit(
                f"payload hash mismatch for {entry['target']}: {digest} != {entry['sha256']}"
            )

        target = REPO_ROOT / entry["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        written = target.read_bytes()
        written_digest = hashlib.sha256(written).hexdigest()
        if len(written) != entry["bytes"] or written_digest != entry["sha256"]:
            raise SystemExit(f"written artifact verification failed for {entry['target']}")
        print(f"{entry['target']}: {written_digest} ({len(written)} bytes)")


if __name__ == "__main__":
    main()
