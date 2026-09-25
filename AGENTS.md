# Project instructions for coding agents

- Preserve unrelated user files and existing work. Keep commits logically scoped;
  do not push changes unless the user requests it.
- Before continuing setup or deployment work, read
  **`docs/agent-handoff.md`** and **`docs/raspberry-pi-setup.md`**.
- The development checkout is on the Mac; the working hardware deployment is at
  `tim@192.168.8.219:/home/tim/bee-mite-detector`. SSH key access worked during setup.
  Recheck connectivity and runtime state rather than assuming they persist.
- Do not blindly follow the historical README's Hailo installation instructions:
  the Pi already has a working newer stack. Do not downgrade drivers, replace
  native Python packages with pip builds, or change boot configuration without need.
- Keep email opt-in. The upstream repository contained published credentials;
  never restore or use them, or enable SMTP authentication debug logging.
- The dashboard is unauthenticated and intended only for a trusted LAN.
