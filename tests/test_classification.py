from netblackbox.models import ProbeResult
from netblackbox.probes import classify


def probes(**overrides: bool) -> ProbeResult:
    values = {
        "modem_ping": True,
        "modem_http": True,
        "modem_https": False,
        "gateway_ping": True,
        "cloudflare_tcp": True,
        "google_dns_tcp": True,
        "http_internet": True,
        "dns_resolution": True,
    }
    values.update(overrides)
    return ProbeResult(**values)


def test_ok() -> None:
    assert classify(probes()) == "OK"


def test_modem_lan_ko() -> None:
    assert classify(probes(modem_ping=False, modem_http=False, modem_https=False)) == "MODEM_LAN_KO"


def test_wan_gateway_ko() -> None:
    assert classify(probes(gateway_ping=False, cloudflare_tcp=False, google_dns_tcp=False, http_internet=False)) == "WAN_GATEWAY_KO"


def test_internet_ko_modem_ok() -> None:
    assert classify(probes(cloudflare_tcp=False, google_dns_tcp=False, http_internet=False)) == "INTERNET_KO_MODEM_OK"


def test_dns_ko() -> None:
    assert classify(probes(dns_resolution=False)) == "DNS_KO"


def test_gateway_may_block_icmp() -> None:
    assert classify(probes(gateway_ping=False)) == "OK_GATEWAY_ICMP_BLOCKED"
