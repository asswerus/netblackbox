# NetBlackBox cross-platform preview

This branch introduces the `src/netblackbox` package and runtime backends for macOS, Linux, and Windows.

Install the preview in editable mode:

```bash
python -m pip install -e .
netblackbox --summary
```

Run the monitor:

```bash
netblackbox
```

The legacy top-level `netblackbox.py` remains as a compatibility launcher for source checkouts.

Automated CI runs the classification tests on macOS, Ubuntu, and Windows with Python 3.10 and 3.12.
