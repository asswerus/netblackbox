from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VerificationResult:
    """Integrity comparison between a bundle and its manifest."""

    verified: tuple[str, ...]
    modified: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not (self.modified or self.missing or self.unexpected)


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read("manifest.json"))
    except KeyError as error:
        raise ValueError("bundle is missing required file: manifest.json") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("bundle contains invalid JSON: manifest.json") from error

    if not isinstance(payload, dict):
        raise ValueError("bundle JSON root must be an object: manifest.json")
    if payload.get("hash_algorithm") != "sha256":
        raise ValueError("bundle manifest uses an unsupported hash algorithm")

    files = payload.get("files")
    if not isinstance(files, dict):
        raise ValueError("bundle manifest files must be an object")
    return payload


def _sha256(archive: zipfile.ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(name) as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(bundle_path: Path) -> VerificationResult:
    """Verify archived files against manifest sizes and SHA-256 digests."""
    if not bundle_path.is_file():
        raise FileNotFoundError(f"bundle not found: {bundle_path}")

    try:
        with zipfile.ZipFile(bundle_path) as archive:
            manifest = _read_manifest(archive)
            entries = manifest["files"]
            archived = set(archive.namelist())
            expected = set(entries)

            missing = tuple(sorted(expected - archived))
            unexpected = tuple(sorted(archived - expected - {"manifest.json"}))
            verified: list[str] = []
            modified: list[str] = []

            for name in sorted(expected & archived):
                entry = entries[name]
                if not isinstance(entry, dict):
                    raise ValueError(f"bundle manifest entry must be an object: {name}")
                expected_size = entry.get("size_bytes")
                expected_digest = entry.get("sha256")
                if not isinstance(expected_size, int) or not isinstance(expected_digest, str):
                    raise ValueError(f"bundle manifest entry is invalid: {name}")

                info = archive.getinfo(name)
                digest = _sha256(archive, name)
                if info.file_size == expected_size and digest == expected_digest:
                    verified.append(name)
                else:
                    modified.append(name)

            return VerificationResult(
                verified=tuple(verified),
                modified=tuple(modified),
                missing=missing,
                unexpected=unexpected,
            )
    except zipfile.BadZipFile as error:
        raise ValueError(f"not a valid ZIP bundle: {bundle_path}") from error


def render_verification(result: VerificationResult) -> str:
    """Render a deterministic terminal summary of an integrity check."""
    lines = ["Bundle integrity", "----------------"]
    lines.extend(f"[OK]         {name}" for name in result.verified)
    lines.extend(f"[MODIFIED]   {name}" for name in result.modified)
    lines.extend(f"[MISSING]    {name}" for name in result.missing)
    lines.extend(f"[UNEXPECTED] {name}" for name in result.unexpected)
    lines.extend(["", f"Result: {'VERIFIED' if result.is_valid else 'FAILED'}"])
    return "\n".join(lines)
