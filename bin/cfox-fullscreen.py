#!/usr/bin/env python3
"""Move the Camoufox window to fullscreen on the LANDSCAPE monitor (HDMI-0).

Invoked by cfox as a background thread once the browser is up.
KWin supports _NET_WM_STATE_FULLSCREEN and _NET_WM_FULLSCREEN_MONITORS, so the
window can be forced fullscreen on one specific monitor.

Argument: <profile-name>   (located via the camoufox-bin process cmdline)
Uses the system python because the Camoufox venv has no python-xlib.
"""
import sys, time, subprocess, os

DISPLAY = os.environ.get("DISPLAY", ":1")
# Landscape monitor (from `xrandr`): HDMI-0 1920x1080 at +0+650, x=0 -> monitor #0.
LANDSCAPE_MON = 0


def _py(code, timeout=15):
    try:
        r = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def find_window(profile):
    """Find the X11 window of the camoufox process that opened this profile."""
    code = r'''
import os, glob
from Xlib import display, X
d = display.Display(os.environ.get("DISPLAY", ":1"))
root = d.screen().root
prof = "__PROFILE__"
pids = set()
for p in glob.glob("/proc/[0-9]*/cmdline"):
    try:
        cl = open(p, "rb").read().decode("utf8", "ignore")
    except Exception:
        continue
    if prof in cl and "camoufox" in cl:
        pids.add(int(p.split("/")[2]))
allp = set(pids)
for p in glob.glob("/proc/[0-9]*/stat"):
    try:
        parts = open(p).read().split()
        if int(parts[3]) in pids:
            allp.add(int(parts[0]))
    except Exception:
        pass
found = []
def walk(w):
    try: kids = w.query_tree().children
    except Exception: return
    for c in kids:
        try:
            pr = c.get_full_property(d.intern_atom("_NET_WM_PID"), X.AnyPropertyType)
            g = c.get_geometry()
            if pr and g.width > 400 and g.height > 200:
                if pr.value[0] in allp:
                    found.append((c.id, g.width, g.height))
            walk(c)
        except Exception: pass
walk(root)
for f in found: print(f[0], f[1], f[2])
'''.replace("__PROFILE__", profile)
    for line in _py(code).strip().split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            try:
                return int(parts[0], 0)
            except ValueError:
                pass
    return None


def force_fullscreen(wid, mon=LANDSCAPE_MON):
    """Send _NET_WM_STATE_FULLSCREEN and _NET_WM_FULLSCREEN_MONITORS to KWin."""
    code = r'''
import os
from Xlib import display, X, protocol
d = display.Display(os.environ.get("DISPLAY", ":1"))
root = d.screen().root
w = d.create_resource_object("window", __WID__)
mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
root.send_event(protocol.event.ClientMessage(
    window=w, client_type=d.intern_atom("_NET_WM_STATE"),
    data=(32, [1, d.intern_atom("_NET_WM_STATE_FULLSCREEN"), 0, 0, 0])),
    event_mask=mask)
d.sync()
root.send_event(protocol.event.ClientMessage(
    window=w, client_type=d.intern_atom("_NET_WM_FULLSCREEN_MONITORS"),
    data=(32, [__MON__, __MON__, __MON__, __MON__, 0])),
    event_mask=mask)
d.sync()
print("ok")
'''.replace("__WID__", str(wid)).replace("__MON__", str(mon))
    return "ok" in _py(code)


def main():
    if len(sys.argv) < 2:
        print("[fs] a profile name is required", flush=True)
        return
    profile = sys.argv[1]
    wid = None
    for _ in range(60):          # up to 30 seconds
        wid = find_window(profile)
        if wid:
            break
        time.sleep(0.5)
    if not wid:
        print(f"[fs] window for '{profile}' not found", flush=True)
        return
    time.sleep(1.0)              # give KWin time to finish mapping
    ok = force_fullscreen(wid)
    print(f"[fs] {profile} wid={hex(wid)} fullscreen={ok}", flush=True)


if __name__ == "__main__":
    main()