# cfm — Camoufox Manager

Terminal UI + CLI for managing many **Camoufox** browser profiles, each with a
distinct, persistent fingerprint and its own proxy.

Built for account-at-scale workflows, where every account must look like a
different device without leaking identity between them.

## Why Camoufox

Dolphin Anty and GoLogin spoof fingerprints at the JavaScript layer only. Values
such as WebGL vendor/renderer, AudioContext, Canvas noise and ClientRects stay
**identical** across profiles. Camoufox spoofs inside the Gecko C++/engine layer,
so those values genuinely differ per profile.

## Features

- **1 profile = 1 permanent fingerprint**, chosen once from 123 real-device
  presets (macOS 30, Windows 75, Linux 18) and reused on every run.
- **One proxy per profile**, stored as its default and changeable at any time.
- **Persistent cookies and logins** — a profile stays signed in after closing.
- **Arrow-key TUI** plus slash commands (`/new`, `/run`, `/proxy`, `/list`, ...).
- **Automatic fullscreen** on the landscape monitor (KWin/X11).
- **Geometry verification** (`cfox-verify`) to catch impossible combinations.

## Install

Requires Python 3.10+ and Camoufox.

```bash
# 1. venv + Camoufox (including the GeoIP database for IP matching)
python3 -m venv ~/.camoufox-venv
~/.camoufox-venv/bin/pip install "camoufox[geoip]" prompt_toolkit questionary
~/.camoufox-venv/bin/camoufox fetch

# 2. scripts
mkdir -p ~/.local/bin
cp bin/* ~/.local/bin/
chmod +x ~/.local/bin/*

# 3. point the shebang at the venv (optional but recommended)
sed -i "1s|.*|#!$HOME/.camoufox-venv/bin/python|" ~/.local/bin/cfox ~/.local/bin/cfm ~/.local/bin/cfox-verify
```

> The Python scripts ship with `#!/usr/bin/env python3`. If you use a venv, replace
> the shebang as in step 3 so the `camoufox` module resolves. `cfm` launches
> `cfox` with `~/.camoufox-venv/bin/python` when that venv exists.
> `cfox-fullscreen.py` runs on the system python and needs `python-xlib`.

Camoufox installs to `~/.cache/camoufox` by default, **a path the system treats
as disposable**. The scripts here deliberately relocate it to
`~/.local/share/camoufox` via `XDG_CACHE_HOME`, because `rm -rf ~/.cache/*` (a
common cleanup command) deletes the ~1.3 GB install. Override the location with
the `CAMOUFOX_HOME` environment variable.

## Usage

```bash
cfm                     # open the TUI
```

Commands inside the TUI:

| Command | Purpose |
|---|---|
| `/new <name>` | create a profile (wizard: OS, then proxy) |
| `/run <name>` | launch a profile; always prompts for a proxy with a `* DEFAULT` entry |
| `/list` | list every profile |
| `/proxy <name>` | change a profile's default proxy |
| `/proxies` | proxy status; `--test` also checks exit IPs |
| `/info <name>` | show UA/GPU/screen/cores detail |
| `/newfp <name>` | regenerate the fingerprint (profile and proxy kept) |
| `/newname <old> <new>` | rename a profile |
| `/rm <name>` | delete a profile |

Tab completes commands; the up/down arrows walk through history.

### Directly from the CLI

```bash
cfox acc1                        # run with the profile's saved default proxy
cfox acc1 --port 1091            # use (and save) a specific proxy
cfox acc1 --noproxy              # run WITHOUT a proxy (real IP), saved as default
cfox acc1 --port 1091 --headless # no window
cfox acc1 --no-fs                # skip automatic fullscreen
cfox --list                      # list profiles
cfox acc1 --show                 # print the stored identity
cfox acc1 --new                  # regenerate the fingerprint (proxy kept)
cfm run acc1 --port 1091 --bg    # same via cfm, in the background
```

Profile names may contain letters, digits, `.`, `_` and `-` only. Background
logs are written to `~/camfox-profiles/_logs/<name>.log` (mode 600).

### Verify geometry

```bash
cfox-verify acc1 acc2 acc3
```

Opens each profile briefly and checks the invariants:

```
outer <= avail <= screen
inner <= outer
clientHeight == innerHeight
chrome > 0
```

A window taller than the screen (`outer > avail`) is an impossible geometry that
detectors flag easily. `cfox` computes every `screen.*` and `window.*` value
itself to prevent it.

## Proxies

This repo does not tie itself to any proxy provider. `cfm` reads ports from
wireproxy config files and offers them as choices:

```
~/surfshark-proxy/configs/*.conf     # one .conf per port
```

Only these two lines matter to the tooling:

```ini
[Socks5]
BindAddress = 127.0.0.1:1091
```

`ss-up` starts every config, `ss-down` stops them, and `cekproxy` prints their
status together with the exit IP location.

For plain HTTP/SOCKS proxies, edit the `kw["proxy"]` block in `cfox` instead.

## systemd (optional)

To start the proxies automatically at boot, use the template unit: one
supervised instance per config, restarted on failure, logs in the journal.

```bash
mkdir -p ~/.config/systemd/user
cp systemd/wireproxy@.service ~/.config/systemd/user/
systemctl --user daemon-reload
for c in ~/surfshark-proxy/configs/*.conf; do
    systemctl --user enable --now "wireproxy@$(basename "$c" .conf).service"
done
loginctl enable-linger "$USER"
journalctl --user -u 'wireproxy@*' -f     # logs
```

`ss-down` stops these units as well as proxies started by `ss-up`.

## Important notes

- **Never put the Camoufox install under `~/.cache`.** That directory is treated
  as disposable; `rm -rf ~/.cache/*` deletes it (this happened once, ~1.3 GB
  lost).
- **`fingerprint_preset` makes `window=` a no-op.** Camoufox uses `from_preset()`,
  which fills `screen.*` but never `window.*`, so the window is generated
  unclamped. `cfox` therefore passes `config=window_geometry(...)` explicitly.
  Writing `window.*` disables all of Camoufox's auto-clamping, so every bound is
  computed by hand.
- **`no_viewport=True` is required.** Without it Playwright pins the viewport to
  1280x720 and a fullscreen window renders the page only in the top-left corner.
- **Commercial proxy IPs always appear on the Spamhaus PBL** (`127.0.0.11`). That
  is not a spam signal — ordinary home IPs are listed too. What matters is that
  `outer <= screen` stays true.
- **Scale.** The preset pool is finite (macOS 27 valid, Linux 17, Windows 70).
  Beyond that, presets get reused.

## License

MIT — see [LICENSE](LICENSE).