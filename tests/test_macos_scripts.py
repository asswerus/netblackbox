from pathlib import Path
import subprocess


def test_macos_shell_scripts_parse() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("install.sh", "migrate-macos.sh", "rollback-macos.sh"):
        result = subprocess.run(["bash", "-n", str(root / name)], capture_output=True, text=True)
        assert result.returncode == 0, f"{name}: {result.stderr}"
