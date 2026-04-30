from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BASE_URL = "https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2023/"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


@dataclass
class BrowseManifest:
    directories: list[str]
    files: list[str]


def build_session():
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    return opener


def register_session(opener) -> None:
    payload = urlencode(
        {
            "first_name": "Ercan",
            "last_name": "Erkalkan",
            "email": "ercan.erkalkan@marmara.edu.tr",
            "institution": "Marmara University",
            "job_title": "Researcher",
            "country": "Turkey",
        }
    ).encode("utf-8")
    request = Request(BASE_URL + "insert.php", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    opener.open(request, timeout=120).read()


def crawl_manifest(opener) -> BrowseManifest:
    seen: set[str] = set()
    queue = [""]
    files: set[str] = set()
    directories: set[str] = {""}
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        url = BASE_URL + "browse.php" + ("" if not current else "?p=" + current.replace(" ", "+"))
        html = opener.open(url, timeout=120).read().decode("utf-8", "ignore")
        parser = LinkParser()
        parser.feed(html)
        for href in parser.links:
            if href.startswith("browse.php?p="):
                target = parse_qs(urlparse(href).query).get("p", [""])[0]
                if target not in directories:
                    directories.add(target)
                    queue.append(target)
            elif href.startswith("download.php?file="):
                target = parse_qs(urlparse(href).query).get("file", [""])[0]
                files.add(target)
    return BrowseManifest(directories=sorted(directories), files=sorted(files))


def bundle_selection(files: Iterable[str]) -> list[str]:
    preferred = [
        "README.pdf",
        "CSV/CSV.zip",
        "CSV/MERGED_CSV.zip",
        "CSV/README.pdf",
        "Supplementary Materials/README.pdf",
        "Supplementary Materials/README_Victims_List.pdf",
        "Supplementary Materials/pcap2csv.zip",
        "Supplementary Materials/tools.zip",
        "example/example.ipynb",
        "PCAP/README_PCAP.pdf",
        "PCAP/PCAP.zip",
    ]
    file_set = set(files)
    return [item for item in preferred if item in file_set]


def download_file(opener, remote_path: str, target_root: Path, chunk_size: int = 1024 * 1024) -> Path:
    local_path = target_root / remote_path.replace("/", "\\")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path
    part_path = local_path.with_name(local_path.name + ".part")
    existing_size = part_path.stat().st_size if part_path.exists() else 0
    url = BASE_URL + "download.php?file=" + remote_path.replace(" ", "+")
    headers = {"User-Agent": "Mozilla/5.0"}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"
    request = Request(url, headers=headers)
    with opener.open(request, timeout=120) as response:
        append_mode = existing_size > 0 and response.headers.get("Content-Range")
        if not append_mode and part_path.exists():
            part_path.unlink()
            existing_size = 0
        with part_path.open("ab" if append_mode else "wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
    if local_path.exists():
        local_path.unlink()
    part_path.rename(local_path)
    return local_path


def sanitize_remote_path(remote_path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", remote_path)


def choose_split_root(split_roots: list[Path], reserve_bytes: int) -> Path:
    candidates: list[tuple[int, Path]] = []
    for root in split_roots:
        root.mkdir(parents=True, exist_ok=True)
        free_bytes = shutil.disk_usage(root).free
        candidates.append((free_bytes, root))
    candidates.sort(key=lambda item: item[0], reverse=True)
    for free_bytes, root in candidates:
        if free_bytes > reserve_bytes:
            return root
    raise OSError(f"No split root has more than {reserve_bytes} free bytes.")


def discover_existing_split_parts(remote_path: str, split_roots: list[Path]) -> list[dict[str, str | int]]:
    relative_dir = Path("ciciot2023_split") / Path(remote_path.replace("/", "\\")).parent
    file_name = Path(remote_path).name
    discovered: list[dict[str, str | int]] = []
    for split_root in split_roots:
        candidate_dir = split_root / relative_dir
        if not candidate_dir.exists():
            continue
        for part_path in sorted(candidate_dir.glob(f"{file_name}.part*")):
            suffix = part_path.suffix
            try:
                index = int(suffix.replace(".part", ""))
            except ValueError:
                continue
            discovered.append(
                {
                    "index": index,
                    "path": str(part_path),
                    "root": str(split_root),
                    "relative_path": str(part_path.relative_to(split_root)),
                    "bytes": part_path.stat().st_size,
                }
            )
    return sorted(discovered, key=lambda item: int(item["index"]))


def download_file_split(
    opener,
    remote_path: str,
    target_root: Path,
    split_roots: list[Path],
    part_size_bytes: int,
    reserve_bytes: int = 1 * 1024 * 1024 * 1024,
    chunk_size: int = 1024 * 1024,
    request_timeout: int = 3600,
) -> Path:
    metadata_dir = target_root / "_split_downloads"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{sanitize_remote_path(remote_path)}.json"
    url = BASE_URL + "download.php?file=" + remote_path.replace(" ", "+")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    relative_dir = Path("ciciot2023_split") / Path(remote_path.replace("/", "\\")).parent
    file_name = Path(remote_path).name
    parts = discover_existing_split_parts(remote_path, split_roots)
    total_bytes = sum(int(part["bytes"]) for part in parts)
    part_index = int(parts[-1]["index"]) if parts else 0

    def flush_metadata() -> None:
        metadata = {
            "remote_path": remote_path,
            "part_size_bytes": part_size_bytes,
            "total_bytes": total_bytes,
            "parts": parts,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def open_next_part(index: int, append: bool = False):
        if append and parts:
            part_path = Path(str(parts[-1]["path"]))
            handle = part_path.open("ab")
            return handle
        split_root = choose_split_root(split_roots, reserve_bytes)
        part_dir = split_root / relative_dir
        part_dir.mkdir(parents=True, exist_ok=True)
        part_path = part_dir / f"{file_name}.part{index:04d}"
        handle = part_path.open("wb")
        parts.append(
            {
                "index": index,
                "path": str(part_path),
                "root": str(split_root),
                "relative_path": str(part_path.relative_to(split_root)),
                "bytes": 0,
            }
        )
        flush_metadata()
        return handle

    bytes_in_part = int(parts[-1]["bytes"]) if parts else 0
    flush_metadata()
    with opener.open(request, timeout=request_timeout) as response:
        bytes_to_skip = total_bytes
        while bytes_to_skip > 0:
            skipped = response.read(min(chunk_size, bytes_to_skip))
            if not skipped:
                raise OSError(f"Unable to skip {bytes_to_skip} previously-downloaded bytes for resume.")
            bytes_to_skip -= len(skipped)

        if parts and bytes_in_part < part_size_bytes:
            handle = open_next_part(part_index, append=True)
        else:
            if parts and bytes_in_part >= part_size_bytes:
                part_index += 1
            handle = open_next_part(part_index)
            bytes_in_part = 0

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            if bytes_in_part + len(chunk) > part_size_bytes:
                remaining = part_size_bytes - bytes_in_part
                if remaining > 0:
                    handle.write(chunk[:remaining])
                    bytes_in_part += remaining
                    total_bytes += remaining
                    parts[-1]["bytes"] = bytes_in_part
                    if total_bytes % (128 * 1024 * 1024) < chunk_size:
                        flush_metadata()
                handle.close()
                flush_metadata()
                part_index += 1
                handle = open_next_part(part_index)
                bytes_in_part = 0
                chunk = chunk[remaining:]
                while len(chunk) > part_size_bytes:
                    handle.write(chunk[:part_size_bytes])
                    bytes_in_part = part_size_bytes
                    total_bytes += part_size_bytes
                    parts[-1]["bytes"] = bytes_in_part
                    handle.close()
                    flush_metadata()
                    part_index += 1
                    handle = open_next_part(part_index)
                    bytes_in_part = 0
                    chunk = chunk[part_size_bytes:]
                if chunk:
                    handle.write(chunk)
                    bytes_in_part += len(chunk)
                    total_bytes += len(chunk)
                    parts[-1]["bytes"] = bytes_in_part
                    if total_bytes % (128 * 1024 * 1024) < chunk_size:
                        flush_metadata()
            else:
                handle.write(chunk)
                bytes_in_part += len(chunk)
                total_bytes += len(chunk)
                parts[-1]["bytes"] = bytes_in_part
                if total_bytes % (128 * 1024 * 1024) < chunk_size:
                    flush_metadata()
        handle.close()
    flush_metadata()
    return metadata_path


def save_manifest(manifest: BrowseManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"directories": manifest.directories, "files": manifest.files}, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register on the official CICIoT2023 form and download official bundles.")
    parser.add_argument("--target", default=str(ROOT / "data" / "raw" / "ciciot2023"), help="Target directory.")
    parser.add_argument(
        "--mode",
        choices=["bundles", "all-files", "split-file"],
        default="bundles",
        help="Download official bundles only, or every exposed file.",
    )
    parser.add_argument("--remote-path", help="Specific remote file path for split-file mode.")
    parser.add_argument(
        "--split-root",
        action="append",
        default=[],
        help="Additional root directory for split-file parts. Can be provided multiple times.",
    )
    parser.add_argument(
        "--part-size-mb",
        type=int,
        default=2048,
        help="Split-file part size in MiB.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Per-request timeout for split-file downloads.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_root = Path(args.target).resolve()
    opener = build_session()
    register_session(opener)
    if args.mode == "split-file":
        if not args.remote_path:
            raise SystemExit("--remote-path is required for split-file mode")
        split_roots = [Path(path).resolve() for path in ([str(target_root)] + args.split_root)]
        metadata_path = download_file_split(
            opener=opener,
            remote_path=args.remote_path,
            target_root=target_root,
            split_roots=split_roots,
            part_size_bytes=args.part_size_mb * 1024 * 1024,
            request_timeout=args.timeout_seconds,
        )
        print(f"split download manifest -> {metadata_path}")
        return
    manifest = crawl_manifest(opener)
    save_manifest(manifest, target_root / "manifest.json")
    selected = bundle_selection(manifest.files) if args.mode == "bundles" else manifest.files
    downloaded: list[str] = []
    for remote_path in selected:
        local_path = download_file(opener, remote_path, target_root)
        print(f"downloaded {remote_path} -> {local_path}")
        downloaded.append(remote_path)
        (target_root / "downloaded_files.json").write_text(json.dumps(downloaded, indent=2), encoding="utf-8")
    print(f"manifest files: {len(manifest.files)}")
    print(f"downloaded files: {len(downloaded)}")


if __name__ == "__main__":
    main()
