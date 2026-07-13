from netblackbox.platforms import LinuxBackend, MacOSBackend, WindowsBackend


def test_backend_names() -> None:
    assert MacOSBackend.name == "macos"
    assert LinuxBackend.name == "linux"
    assert WindowsBackend.name == "windows"


def test_ping_commands_are_platform_specific() -> None:
    assert MacOSBackend().ping_command("1.1.1.1")[0] == "/sbin/ping"
    assert LinuxBackend().ping_command("1.1.1.1")[0] == "ping"
    assert WindowsBackend().ping_command("1.1.1.1")[:2] == ["ping", "-n"]
