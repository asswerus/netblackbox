from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DiagnosticCommand:
    name: str
    args: list[str]
    timeout: int = 10


class PlatformBackend:
    name = "generic"

    def ping_command(self, host: str) -> list[str]:
        raise NotImplementedError

    def default_gateway(self) -> str | None:
        raise NotImplementedError

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        raise NotImplementedError

    @staticmethod
    def run(args: list[str], timeout: int = 5) -> tuple[int, str]:
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
            return proc.returncode, (proc.stdout + ("\nSTDERR:\n" + proc.stderr if proc.stderr else "")).strip()
        except Exception as exc:
            return 125, f"{type(exc).__name__}: {exc}"


class MacOSBackend(PlatformBackend):
    name = "macos"

    def ping_command(self, host: str) -> list[str]:
        return ["/sbin/ping", "-n", "-c", "1", "-W", "1000", host]

    def default_gateway(self) -> str | None:
        code, output = self.run(["/sbin/route", "-n", "get", "default"])
        if code == 0:
            for line in output.splitlines():
                if line.strip().startswith("gateway:"):
                    return line.split(":", 1)[1].strip()
        return None

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return [
            DiagnosticCommand("route_default", ["/sbin/route", "-n", "get", "default"]),
            DiagnosticCommand("routes", ["/usr/sbin/netstat", "-rn"]),
            DiagnosticCommand("arp", ["/usr/sbin/arp", "-an"]),
            DiagnosticCommand("dns", ["/usr/sbin/scutil", "--dns"]),
            DiagnosticCommand("interfaces", ["/sbin/ifconfig"]),
            DiagnosticCommand("traceroute", ["/usr/sbin/traceroute", "-n", "-m", "12", "-w", "1", "1.1.1.1"], 20),
        ]


class LinuxBackend(PlatformBackend):
    name = "linux"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", "-n", "-c", "1", "-W", "1", host]

    def default_gateway(self) -> str | None:
        code, output = self.run(["ip", "route", "show", "default"])
        if code == 0:
            fields = output.split()
            if "via" in fields:
                return fields[fields.index("via") + 1]
        return None

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        commands = [
            DiagnosticCommand("routes", ["ip", "route"]),
            DiagnosticCommand("addresses", ["ip", "addr"]),
            DiagnosticCommand("neighbours", ["ip", "neigh"]),
            DiagnosticCommand("resolv_conf", ["cat", "/etc/resolv.conf"]),
        ]
        if shutil.which("resolvectl"):
            commands.append(DiagnosticCommand("resolved", ["resolvectl", "status"]))
        trace = shutil.which("traceroute") or shutil.which("tracepath")
        if trace:
            commands.append(DiagnosticCommand("traceroute", [trace, "1.1.1.1"], 20))
        return commands


class WindowsBackend(PlatformBackend):
    name = "windows"

    def ping_command(self, host: str) -> list[str]:
        return ["ping", "-n", "1", "-w", "1000", host]

    def default_gateway(self) -> str | None:
        script = "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop"
        code, output = self.run(["powershell", "-NoProfile", "-Command", script])
        return output.strip() if code == 0 and output.strip() else None

    def diagnostics(self, modem_ip: str, gateway_ip: str) -> list[DiagnosticCommand]:
        return [
            DiagnosticCommand("ipconfig", ["ipconfig", "/all"]),
            DiagnosticCommand("routes", ["route", "print"]),
            DiagnosticCommand("arp", ["arp", "-a"]),
            DiagnosticCommand("net_ip_configuration", ["powershell", "-NoProfile", "-Command", "Get-NetIPConfiguration | Format-List *"]),
            DiagnosticCommand("dns_servers", ["powershell", "-NoProfile", "-Command", "Get-DnsClientServerAddress | Format-Table -AutoSize"]),
            DiagnosticCommand("tracert", ["tracert", "-d", "-h", "12", "1.1.1.1"], 30),
        ]


def current_backend() -> PlatformBackend:
    system = platform.system()
    if system == "Darwin":
        return MacOSBackend()
    if system == "Linux":
        return LinuxBackend()
    if system == "Windows":
        return WindowsBackend()
    raise RuntimeError(f"Unsupported operating system: {system}")
