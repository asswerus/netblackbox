from dataclasses import asdict

from netblackbox.models import Sample


def test_sample_context_defaults_preserve_existing_callers() -> None:
    sample = Sample(
        timestamp="2026-07-13T23:45:00+02:00",
        state="OK",
        gateway_ip="192.0.2.1",
        probes={"gateway_ping": True},
    )

    assert sample.raw_state == "OK"
    assert sample.severity is None
    assert sample.sampling_mode == "normal"
    assert sample.sampling_interval_seconds is None


def test_sample_preserves_observed_and_confirmed_state() -> None:
    sample = Sample(
        timestamp="2026-07-13T23:45:00.500+02:00",
        state="OK",
        observed_state="WAN_GATEWAY_KO",
        severity="INFO",
        sampling_mode="fast",
        sampling_interval_seconds=0.5,
        gateway_ip="192.0.2.1",
        probes={"gateway_ping": False},
    )

    assert sample.raw_state == "WAN_GATEWAY_KO"
    assert asdict(sample)["sampling_mode"] == "fast"
    assert asdict(sample)["sampling_interval_seconds"] == 0.5
