from pathlib import Path
import shutil
import subprocess

import pytest


def test_macos_shell_scripts_parse() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available on this runner")

    root = Path(__file__).resolve().parents[1]
    for name in ("install.sh", "migrate-macos.sh", "rollback-macos.sh"):
        result = subprocess.run(
            [bash, "-n", str(root / name)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"
