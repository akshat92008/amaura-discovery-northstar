"""
Fetch and extract Alibaba Cluster Trace v2018 datasets:
- machine_meta.tar.gz
- container_meta.tar.gz
"""

import os
import sys
import urllib.request
import tarfile
import hashlib
import io

BASE_URL = "http://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces"
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))

FILES = [
    "machine_meta.tar.gz",
    "container_meta.tar.gz"
]

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest = {}

    for fname in FILES:
        url = f"{BASE_URL}/{fname}"
        out_tar = os.path.join(DATA_DIR, fname)
        print(f"Downloading {fname} from {url}...")
        urllib.request.urlretrieve(url, out_tar)
        tar_sha = sha256_file(out_tar)
        size_bytes = os.path.getsize(out_tar)
        print(f"  Downloaded: {size_bytes} bytes, SHA256: {tar_sha}")

        print(f"Extracting {fname}...")
        with tarfile.open(out_tar, "r:gz") as tar:
            for member in tar.getmembers():
                tar.extract(member, path=DATA_DIR)
                extracted_path = os.path.join(DATA_DIR, member.name)
                ext_sha = sha256_file(extracted_path)
                ext_size = os.path.getsize(extracted_path)
                print(f"  Extracted: {member.name} ({ext_size} bytes, SHA256: {ext_sha})")
                manifest[member.name] = {
                    "source_archive": fname,
                    "archive_sha256": tar_sha,
                    "extracted_sha256": ext_sha,
                    "size_bytes": ext_size
                }

    print("\nAlibaba Cluster Trace v2018 extraction complete.")
    for k, v in manifest.items():
        print(f"{k}: {v['size_bytes']} bytes, SHA256={v['extracted_sha256']}")

if __name__ == "__main__":
    main()
