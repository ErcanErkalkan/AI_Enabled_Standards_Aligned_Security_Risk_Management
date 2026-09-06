from __future__ import annotations
import base64, gzip, hashlib, json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "software" / "r1_payload" / "manifest.json"

def main() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in entries:
        payload_path = REPO_ROOT / entry["payload"]
        target = REPO_ROOT / entry["target"]
        data = gzip.decompress(base64.b64decode(payload_path.read_text(encoding="ascii").strip()))
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            raise SystemExit(f"payload hash mismatch for {entry['target']}: {digest} != {entry['sha256']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written = hashlib.sha256(target.read_bytes()).hexdigest()
        if written != entry["sha256"]:
            raise SystemExit(f"written hash mismatch for {entry['target']}: {written} != {entry['sha256']}")
        print(f"{entry['target']}: {written}")

if __name__ == "__main__":
    main()
