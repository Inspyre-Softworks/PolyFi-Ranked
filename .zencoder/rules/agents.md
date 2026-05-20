---
description: PolyFi Ranked runtime and UI architecture
alwaysApply: true
---

# PolyFi: Ranked Runtime Architecture

## Overview

PolyFi: Ranked is organized around a Windows runtime bootstrapper, a Wi-Fi
preference service, and a small Tk-based settings and notification UI.

## Main Components

### Application bootstrap

- `wifi_pref_manager.app.Application` handles CLI parsing, config loading,
  detached tray startup, splash behavior, and single-instance coordination.

### Runtime service

- `wifi_pref_manager.service.WiFiPreferenceService` evaluates available Wi-Fi
  networks, enforces preferred ordering, and reacts to Ethernet state.

### Windows shell helpers

- `wifi_pref_manager.windows_shell` resolves the preferred runtime executable
  and builds Start Menu launch targets.

### Tk and tray UI

- `wifi_pref_manager.ui.tray` manages the tray icon and menu actions.
- `wifi_pref_manager.ui.settings` manages the settings window.
- `wifi_pref_manager.ui.dialogs` owns the shared Tk UI thread and reusable
  dialogs.
- `wifi_pref_manager.ui.splash` resolves and displays the startup splash.

## Important Rule

All Tk work must stay on the shared UI thread. New dialogs or settings windows
should dispatch through `run_on_ui_thread(...)` instead of creating ad hoc Tk
roots on worker threads.
