from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from netblackbox.bundle_verifier import verify_bundle


def write_bundle(
    path: Path,
    *,
    files: dict[str, bytes] | None = None,
    archived_files: dict[str, bytes] | None = None,
) -> None:
    expected_files = files or {"metadata.json": b"{}", "summary.json": b"{}"}
    actual_files = archived_files or expected_files
    manifest = {
        "manifest_version": 1,
        "hash_algorithm": "sha256",
        "manifest_includes_itself": False,
        "files": {
            name: {
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in expected_files.items()
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in actual_files.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", json.dumps(manifest))


def test_verify_bundle_accepts_matching_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    write_bundle(bundle)

    result = verify_bundle(bundle)

    assert result.is_valid
    assert result.verified == ("metadata.json", "summary.json")
    assert result.modified == ()
    assert result.missing == ()
    assert result.unexpected == ()


def test_verify_bundle_reports_modified_missing_and_unexpected_files(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    expected = {
        "metadata.json": b"original",
        "summary.json": b"expected",
        "playback/7.json": b"sample",
    }
    archived = {
        "metadata.json": b"modified",
        "summary.json": b"expected",
        "extra.txt": b"unexpected",
    }
    write_bundle(bundle, files=expected, archived_files=archived)

    result = verify_bundle(bundle)

    assert not result.is_valid
    assert result.verified == ("summary.json",)
    assert result.modified == ("metadata.json",)
    assert result.missing == ("playback/7.json",)
    assert result.unexpected == ("extra.txt",)


def test_verify_bundle_rejects_missing_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("metadata.json", "{}")

    with pytest.raises(ValueError, match="missing required file: manifest.json"):
        verify_bundle(bundle)


def test_verify_bundle_rejects_malformed_manifest(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", "not-json")

    with pytest.raises(ValueError, match="invalid JSON: manifest.json"):
        verify_bundle(bundle)


def test_verify_bundle_rejects_unsupported_hash_algorithm(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    manifest = {"hash_algorithm": "md5", "files": {}}
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(ValueError, match="unsupported hash algorithm"):
        verify_bundle(bundle)
