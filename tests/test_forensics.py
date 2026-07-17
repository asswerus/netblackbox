from nbb.app import severity_for
from nbb.models import ProbeResult


def test_probe_result_exposes_latency_without_breaking_boolean_state() -> None:
    result = ProbeResult(
        modem_ping=True,
        modem_http=False,
        modem_https=False,
        gateway_ping=False,
        cloudflare_tcp=True,
        google_dns_tcp=False,
        http_internet=False,
        dns_resolution=True,
        modem_ping_ms=4.2,
        cloudflare_tcp_ms=18.7,
    )
    assert result.modem_reachable is True
    assert result.internet_reachable is True
    assert result.modem_ping_ms == 4.2


def test_severity_escalates_with_duration() -> None:
    assert severity_for("DNS_KO", 10) == "WARNING"
    assert severity_for("DNS_KO", 120) == "MAJOR"
    assert severity_for("INTERNET_KO_MODEM_OK", 30) == "MAJOR"
    assert severity_for("INTERNET_KO_MODEM_OK", 180) == "CRITICAL"
    assert severity_for("MODEM_LAN_KO", 5) == "MAJOR"
    assert severity_for("MODEM_LAN_KO", 45) == "CRITICAL"
