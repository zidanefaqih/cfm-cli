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
- Optional fullscreen on the landscape monitor (KWin/X11) via `cfox --fs`.
- **Geometry verification** (`cfox-verify`) to catch impossible combinations.

## Install

Requires Python 3.10+ and Camoufox.

### Linux

```bash
git clone https://github.com/zidanefaqih/cfm-cli.git
cd cfm-cli

python3 -m venv ~/.camoufox-venv
~/.camoufox-venv/bin/python -m pip install -U pip
~/.camoufox-venv/bin/python -m pip install "camoufox[geoip]" prompt_toolkit questionary

# Keep the browser outside the disposable ~/.cache directory.
XDG_CACHE_HOME="$HOME/.local/share/camoufox" ~/.camoufox-venv/bin/python -m camoufox fetch

# Optional: install the scripts on PATH.
mkdir -p ~/.local/bin
cp bin/* ~/.local/bin/
chmod +x ~/.local/bin/*

# Optional: extra real-GPU identities (see 'Extra GPUs' below).
mkdir -p ~/.local/share/cfm-cli
cp extras/gpus.json ~/.local/share/cfm-cli/

# Point the shebang at the venv.
sed -i "1s|.*|#!$HOME/.camoufox-venv/bin/python|" ~/.local/bin/cfox ~/.local/bin/cfm ~/.local/bin/cfox-verify

# Or run directly from the clone.
~/.camoufox-venv/bin/python bin/cfm
```

`cfm` launches the adjacent `cfox` using the venv interpreter. Keep both files
together if you copy or move them.

### Windows 10/11

Install Git, Python 3.10+, and `curl.exe` first. In PowerShell:

```powershell
git clone https://github.com/zidanefaqih/cfm-cli.git
cd cfm-cli

py -3.12 -m venv "$HOME\.camoufox-venv"
$python = "$HOME\.camoufox-venv\Scripts\python.exe"
& $python -m pip install -U pip
& $python -m pip install "camoufox[geoip]" prompt_toolkit questionary
& $python -m camoufox fetch

& $python .\bin\cfm
```

Use `py -3.10`, `py -3.11`, or another installed Python 3.10+ version if
`py -3.12` is unavailable. Profiles are stored under your user folder and
remote proxy configs under `%LOCALAPPDATA%\cfm-cli\configs`. Local WireGuard,
`ss-up`/`ss-down`, and systemd helpers are Linux-only; on Windows, choose a
remote proxy in `cfm` or use no proxy. macOS install steps are not documented
yet. `curl.exe` is used for proxy health checks; Windows 10/11 usually includes
it, otherwise install curl and add it to `PATH`.

Camoufox installs to `~/.cache/camoufox` by default, **a path the system treats
as disposable**. The scripts here deliberately relocate it to
`~/.local/share/camoufox` on Linux via `XDG_CACHE_HOME`, because `rm -rf ~/.cache/*`
(a common cleanup command) deletes the ~1.3 GB install. On Windows Camoufox uses
its standard `%LOCALAPPDATA%` cache location.

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
| `/addproxy [label]` | add a remote proxy (host, port, username, password) |
| `/rmproxy [label]` | delete a remote proxy |
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
cfox acc1 --fs                   # opt into delayed fullscreen on X11/KWin
cfox --list                      # list profiles
cfox acc1 --show                 # print the stored identity
cfox acc1 --new                  # regenerate the fingerprint (proxy kept)
cfm run acc1 --port 1091 --bg    # same via cfm, in the background
```

Profile names may contain letters, digits, `.`, `_` and `-` only. Background
logs are written to `~/camfox-profiles/_logs/<name>.log` (mode 600 on Unix).

### Verify runtime screen geometry

```bash
cfox-verify acc1 acc2 acc3
```

Opens each profile briefly and checks the active monitor dimensions, available
screen bounds, and that the document viewport matches the native browser window.

```
screen == active monitor
avail < screen
inner <= outer
clientHeight == innerHeight
```

`screen.*` follows the largest attached display in CSS pixels when the browser
starts. `window.*` remains native, so resizing the browser also resizes the page
viewport. The stored preset screen remains visible as profile metadata, but it is
not used for the active display dimensions.

## Extra GPUs (extras/gpus.json)

Camoufox's preset pool repeats the same handful of renderer strings, and the
Linux pool (17 valid presets) is small enough to run out. `extras/gpus.json`
adds identities drawn from fpgen's pinned model of devices **Firefox has
actually been recorded reporting**. Each entry carries its own recorded WebGL
data (WebGL1 + WebGL2), so it needs no row in Camoufox's `webgl_data.db`;
`cfox`, `cfm` and `cfox-verify` serve it at launch through `bin/cfm_gpu.py`.

Select one explicitly while creating a profile:

```bash
cfox acc11 --os linux --gpu gtx480
cfm new acc11 --os linux --gpu gtx480
```

`--gpu` matches a case-insensitive substring of the vendor or renderer with
spaces ignored (`gtx480` == `GTX 480`). Without it, extras take part in the
normal random pool.

**Modern model names are absent on purpose.** Gecko's `SanitizeRenderer`
collapses every GeForce 900-4000-series, Quadro and RTX part into a single
representative string before a page sees it, so stock Firefox never reports
"RTX 4060", "GTX 1050" or "RTX 3050". Measured on a real GTX 1660 SUPER:
stock Firefox (the default `webgl.sanitize-unmasked-renderer=true`) reports
`NVIDIA GeForce GTX 980, or similar`, and only with that pref set to `false`
does it report `NVIDIA GeForce GTX 1660 SUPER/PCIe/SSE2`.

Camoufox's own spoofing bypasses the sanitizer, so a profile *can* be made to
say "RTX 4060" — but that is the renderer of a user who turned the pref off, a
rare configuration, and no recorded WebGL parameters exist for such a GPU, so
they would be borrowed from another device. That is a masking tell, not
variety, so `--gpu rtx4060` is rejected. The authentic set is the bucket list in
Mozilla's `dom/canvas/SanitizeRenderer.cpp`; add GPUs from there.

Add a GPU only after confirming Firefox reports it (fpgen's `gpu` node, or a
real machine). An entry needs `os`, `vendor`, `renderer`, `preset_id`, a
`preset` with `navigator`/`screen`/`webgl{unmaskedVendor,unmaskedRenderer}`,
and the full `webgl_data` blob.

## WebGL readback noise (bin/cfm_readpixels.py)

Spoofing the WebGL *identity* is not enough, because the frame itself is still
drawn by the physical GPU. `gl.readPixels()` returns that framebuffer
byte-for-byte, and Camoufox does not perturb it. Measured on one machine: two
profiles carrying different personas returned **identical** `readPixels`
output, and it was also bit-identical to the same probe run in stock Chrome on
the host GPU. So every profile on a machine shares one render fingerprint, and
that fingerprint is the host's real GPU — enough for a site that hashes
rendered pixels to link all the profiles, and to link them to the operator.

`bin/cfm_readpixels.py` closes the `readPixels` path the same way Camoufox
already handles 2D canvas: a +-1 LSB perturbation applied on readback, seeded
per profile and stored as `.cfm-readpixels-seed` inside the profile directory.

Properties: stable per profile (two runs return identical bytes), different
between profiles, RGB only (alpha untouched), and non-destructive — only the
returned buffer changes, never the framebuffer. `Function.prototype.toString`
is proxied so `readPixels` still reports as `[native code]`.

```bash
cfox lin89            # prints: readPixels: noise on (seed e0f5be5b)
CFM_READPIXELS_NOISE=0 cfox lin89   # run without the patch (debugging)
```

**Not covered yet:** `canvas.toDataURL()` / `toBlob()` called directly on a
WebGL canvas, and drawing a WebGL canvas into a 2D canvas and reading it back
with `getImageData()`. Both still return the unperturbed physical-GPU pixels.
Patching those paths means wrapping 2D-context readback, which risks both
performance and breaking ordinary web apps, so it was left out deliberately.

**Also not covered: child frames.** On Firefox this init script only reaches
the main frame. A page that runs its WebGL fingerprint inside an iframe never
sees the noise. Confirmed against pixelscan.net: with the noise installed its
reported `WebGL Hash` does not change at all, and instrumenting the page
records zero WebGL calls in the main frame even though the site clearly
collects canvas data. So treat this as a real improvement on the readback path,
not as a fix for any specific site.

Check it yourself:

```bash
cfm-rp-test lin89 lin94             # two profiles -> two different hashes
cfm-rp-test lin89 lin94 --no-patch  # control -> one hash for both
```

A pixel-exact uniformity check (clear to an exact colour, read it back, expect
an exact match) would notice the noise. That is the cost of not leaking the
GPU, and it is the same trade-off Camoufox already makes for 2D canvas.

## Proxies

This repo does not tie itself to any proxy provider. `cfm` reads ports from
wireproxy config files and offers them as choices:

```
~/surfshark-proxy/configs/*.conf     # Linux: one .conf per local port
```

Only these two lines matter to the tooling:

```ini
[Socks5]
BindAddress = 127.0.0.1:1091
```

`ss-up` starts every config, `ss-down` stops them, and `cekproxy` prints their
status together with the exit IP location.

### Remote proxies (Webshare and similar)

Add a remote proxy with a username/password from the TUI (also the supported
proxy workflow on Windows):

```
cfm> /addproxy webshare-us1
  Paste proxy (host:port:user:pass, user:pass@host:port or URL)
  or press ENTER to fill in the fields one by one:
```

- Accepted formats: `host:port:user:pass` (Webshare's download list),
  `user:pass@host:port`, `http://user:pass@host:port`, `host:port`.
- The wizard tests the proxy (exit IP + location) before saving and can set it
  as a profile's default right away. Assign it later with `/proxy <profile> <label>`.
- Stored as `~/surfshark-proxy/configs/<label>.url` on Linux or
  `%LOCALAPPDATA%\cfm-cli\configs\<label>.url` on Windows; credentials are
  percent-encoded. Unix files use mode 600; Windows uses the user-profile ACL.
- Firefox cannot authenticate to SOCKS5 proxies, so use **HTTP** for
  proxies with a username/password; the wizard offers to switch.
- `/proxies --test` checks remote proxies too; `/rmproxy <label>` deletes one.
- Scripted: `cfm addproxy <label> host:port:user:pass` (the password ends up in
  your shell history).
- `cfox` resolves the exit IP through the proxy before launching and refuses to
  start when the proxy does not work.

## systemd (Linux only, optional)

To start the proxies automatically at boot, use the template unit: one
supervised instance per config, restarted on failure, logs in the journal.

```bash
mkdir -p ~/.config/systemd/user
cp systemd/wireproxy@.service systemd/surfshark-proxy.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now surfshark-proxy.service
systemctl --user restart surfshark-proxy.service
loginctl enable-linger "$USER"
journalctl --user -u 'wireproxy@*' -f     # logs
```

This also migrates the older launcher: each config is now a separate supervised
unit, so a temporary DNS failure or a dead tunnel is retried automatically.

`ss-down` stops these units as well as proxies started by `ss-up`.

## Important notes

- **Linux cache location.** The scripts keep Camoufox outside `~/.cache`, which
  some cleanup commands delete. Windows uses Camoufox's standard AppData cache.
- **Runtime screen and resize behavior.** `cfox` overrides the preset's
  `screen.*` dimensions with the active monitor's CSS-pixel dimensions, then
  leaves `window.*` native. Profiles on the same display therefore share screen
  dimensions, and the page viewport follows browser-window resizing.
- **`no_viewport=True` is required.** Without it Playwright pins the viewport to
  1280x720 and a fullscreen window renders the page only in the top-left corner.
- **Commercial proxy IPs always appear on the Spamhaus PBL** (`127.0.0.11`). That
  is not a spam signal — ordinary home IPs are listed too. What matters is that
  `outer <= screen` stays true.
- **Scale.** The preset pool is finite (macOS 27 valid, Linux 17, Windows 70).
  Profile creation refuses to reuse a preset ID; choose another OS or add more
  valid presets when that OS's pool is exhausted.

## License

MIT — see [LICENSE](LICENSE).
