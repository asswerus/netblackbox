from nbb.timeline import render_event_timeline


def test_timeline_renders_event_and_enriched_samples() -> None:
    page = render_event_timeline(
        {
            "event": {"id": 42, "state": "WAN_GATEWAY_KO"},
            "samples": [
                {
                    "timestamp": "2026-07-14T00:30:00+02:00",
                    "phase": "pre",
                    "state": "OK",
                    "raw_state": "WAN_GATEWAY_KO",
                    "sampling_mode": "fast",
                    "sampling_interval_seconds": 0.5,
                    "probes": {"gateway_ping": False},
                }
            ],
        }
    )

    assert "NetBlackBox event 42" in page
    assert "WAN_GATEWAY_KO" in page
    assert 'data-filter="active"' in page
    assert 'type="application/json"' in page
    assert '"sampling_mode":"fast"' in page


def test_timeline_escapes_event_metadata_and_script_terminators() -> None:
    page = render_event_timeline(
        {
            "event": {"id": "<42>", "state": "</script><b>broken</b>"},
            "samples": [],
        }
    )

    assert "Event &lt;42&gt;" in page
    assert "&lt;/script&gt;&lt;b&gt;broken&lt;/b&gt;" in page
    assert "</script><b>broken" not in page
    assert "<\\/script>" in page
