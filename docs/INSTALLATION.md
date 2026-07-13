# Installation status

The package core supports macOS, Linux, and Windows.

Service installers are being added separately:

- macOS: `launchd` installer already exists and will be adapted to the package entry point.
- Linux: planned `systemd` user service.
- Windows: planned Task Scheduler installer, followed by an optional native service wrapper.

For development and manual execution on every supported platform:

```bash
python -m pip install -e .
netblackbox
```
