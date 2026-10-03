"""Generate extra GPU entries for extras/gpus.json (companion to cfm_gpu.py).

An entry's webgl_data must be the WebGL1+WebGL2 values a real Firefox would
serve for that (vendor, renderer) pair, in the same shape as the rows of
Camoufox's bundled webgl_data.db. Two sources, tried in order:

1. The bundled database itself. When the pair is already recorded there
   (any OS weight > 0), its stored data is reused verbatim -- it is exactly
   what Camoufox would serve, so nothing has to be synthesized.
2. fpgen's pinned model (scrapfly/fingerprint-generator, model-2/2026),
   conditioned on browser=Firefox, os and the gpu pair. Only pairs Firefox
   has really been recorded reporting ever reach this point (see AF-004);
   fpgen has no data for made-up names, so no invented GPU can slip in.

The navigator/screen parts of the generated preset stub follow the bundled
preset pool's conventions (Firefox 149-152 UAs, cores 2-16, screens that fit
a 1920x1080 monitor).

Usage (from the repo root, with the Camoufox venv for db access and fpgen
installed for source 2):
    bin/cfm_gpu_gen.py list
    bin/cfm_gpu_gen.py add --os linux --preset-id hd5850 \
        --vendor AMD --renderer 'Radeon HD 5850, or similar'
    bin/cfm_gpu_gen.py add --os linux --preset-id 8800gtx \
        --vendor 'NVIDIA Corporation' --renderer 'GeForce 8800 GTX, or similar' \
        --cores 4 --ua 149.0
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
GPUS_JSON = HERE.parent / "extras" / "gpus.json"
CAMOUFOX_SITE = pathlib.Path.home() / ".camoufox-venv/lib/python3.12/site-packages/camoufox"
DB_PATH = CAMOUFOX_SITE / "webgl/webgl_data.db"
FPGEN_HINT = (
    "fpgen is not installed in this python. Install it with:\n"
    "  git clone --depth 1 https://github.com/scrapfly/fingerprint-generator /tmp/fpgen\n"
    "  python3 -m venv /tmp/fpgen-venv && /tmp/fpgen-venv/bin/pip install /tmp/fpgen\n"
    "then re-run with /tmp/fpgen-venv/bin/python"
)

OS_TO_DB = {"linux": "lin", "windows": "win", "macos": "mac"}

# WebGL param 37445/37446 = UNMASKED_VENDOR_WEBGL / UNMASKED_RENDERER_WEBGL.
# The bundled db stores the pair's vendor/renderer strings there; fpgen leaves
# them null, and an explicit null overrides Camoufox's own injection so pages
# read `null` from WEBGL_debug_renderer_info. Always stamp the real strings.
UNMASKED_VENDOR_PARAM, UNMASKED_RENDERER_PARAM = "37445", "37446"


def sanitize_params(params, vendor, renderer):
    """Make a parameters dict safe for the Juggler config.

    Integers beyond int64 (e.g. uint64 timestamps like 18446744073709552000,
    recorded for param 37137) are rejected with "Integer exceeds 64-bit
    range". The bundled db stores those as floats (1.8446744073709552e+19) --
    which is also all a JS double could represent -- so do the same.
    """
    out = {}
    for k, v in params.items():
        if isinstance(v, int) and not -(2**63) <= v <= 2**63 - 1:
            v = float(v)
        out[k] = v
    out[UNMASKED_VENDOR_PARAM] = vendor
    out[UNMASKED_RENDERER_PARAM] = renderer
    return out


def db_webgl_data(vendor, renderer, os_name):
    """Return the pair's recorded data from the bundled webgl_data.db, or None."""
    if not DB_PATH.is_file():
        return None
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT data FROM webgl_fingerprints "
            "WHERE vendor = ? AND renderer = ? AND "
            + OS_TO_DB[os_name]
            + " > 0",
            (vendor, renderer),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
    finally:
        conn.close()
    for pre in ("webGl:", "webGl2:"):
        key = pre + "parameters"
        if key in data:
            data[key] = sanitize_params(data[key], vendor, renderer)
    return data


def fpgen_webgl_data(vendor, renderer, os_name):
    """Generate the pair's WebGL data from fpgen's pinned model."""
    try:
        from fpgen import trace
    except ImportError:
        sys.exit(f"[!] {FPGEN_HINT}")

    result = trace(
        ["webgl", "webgl2"],
        {"browser": "Firefox", "os": os_name, "gpu": {"vendor": vendor, "renderer": renderer}},
    )
    if not result["webgl"] or not result["webgl2"]:
        sys.exit(f"[!] fpgen has no webgl data for {vendor} / {renderer}")
    w, w2 = result["webgl"][0].value, result["webgl2"][0].value

    def params(p):
        return sanitize_params({k: v["value"] for k, v in p.items()}, vendor, renderer)

    def spf(items):
        return {f"{i['shaderType']},{i['precisionType']}": i["r"] for i in items}

    return {
        "webGl:vendor": vendor,
        "webGl:renderer": renderer,
        "webGl:contextAttributes": w["contextAttributes"],
        "webGl:parameters": params(w["params"]),
        "webGl:supportedExtensions": w["supportedExtensions"],
        "webGl:shaderPrecisionFormats": spf(w["shaderPrecisionFormats"]),
        "webGl2:contextAttributes": w2["contextAttributes"],
        "webGl2:parameters": params(w2["params"]),
        "webGl2:supportedExtensions": w2["supportedExtensions"],
        "webGl2:shaderPrecisionFormats": spf(w2["shaderPrecisionFormats"]),
        "webGl2Enabled": True,
    }


UA_BY_OS = {
    "linux": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:{v}) Gecko/20100101 Firefox/{v}",
    "windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}) Gecko/20100101 Firefox/{v}",
}
PLATFORM_BY_OS = {"linux": "Linux x86_64", "windows": "Win32"}


def preset_stub(os_name, vendor, renderer, cores, ua_version, screen):
    sw, sh = screen
    return {
        "navigator": {
            "userAgent": UA_BY_OS[os_name].format(v=ua_version),
            "platform": PLATFORM_BY_OS[os_name],
            "hardwareConcurrency": cores,
            "maxTouchPoints": 0,
        },
        "screen": {
            "width": sw,
            "height": sh,
            "colorDepth": 24,
            "availWidth": sw,
            "availHeight": sh,
            "devicePixelRatio": 1,
        },
        "webgl": {"unmaskedVendor": vendor, "unmaskedRenderer": renderer},
    }


def screen_value(text):
    try:
        w, h = (int(x) for x in text.lower().split("x"))
        return (w, h) if 0 < w <= 1920 and 0 < h <= 1080 else None
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description="Add extra real-GPU entries to extras/gpus.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show current entries")
    a = sub.add_parser("add", help="add one entry")
    a.add_argument("--os", required=True, choices=["linux", "windows", "macos"])
    a.add_argument("--preset-id", required=True, help="short id, e.g. hd5850 (no os:extra: prefix)")
    a.add_argument("--vendor", required=True)
    a.add_argument("--renderer", required=True)
    a.add_argument("--cores", type=int, default=8, help="hardwareConcurrency (default 8)")
    a.add_argument("--ua", default="150.0", help="Firefox version in the UA (default 150.0)")
    a.add_argument("--screen", default="1920x1080", help="preset screen WxH (default 1920x1080)")
    a.add_argument("--force", action="store_true", help="replace an existing entry with the same preset_id")
    args = ap.parse_args()

    pack = json.loads(GPUS_JSON.read_text())
    gpus = pack.setdefault("gpus", [])

    if args.cmd == "list":
        for g in gpus:
            src = "db" if db_webgl_data(g["vendor"], g["renderer"], g["os"]) else "fpgen"
            print(f"{g['preset_id']:<28} {g['vendor']} | {g['renderer']}  [{src}]")
        return

    if not 2 <= args.cores <= 16:
        sys.exit("[!] --cores must be 2..16 (bundled presets stay in that range)")
    screen = screen_value(args.screen)
    if not screen:
        sys.exit("[!] --screen must be WxH and fit a 1920x1080 monitor")

    pid = f"{args.os}:extra:{args.preset_id}"
    if any(g.get("preset_id") == pid for g in gpus):
        if not getattr(args, "force", False):
            sys.exit(f"[!] {pid} already exists in {GPUS_JSON} (use --force to replace)")
        gpus[:] = [g for g in gpus if g.get("preset_id") != pid]

    data = db_webgl_data(args.vendor, args.renderer, args.os)
    source = "camoufox bundled webgl_data.db (recorded row)"
    if data is None:
        data = fpgen_webgl_data(args.vendor, args.renderer, args.os)
        source = "fpgen model-2/2026 trace (browser=Firefox)"
    if data.get("webGl:vendor") != args.vendor or data.get("webGl:renderer") != args.renderer:
        sys.exit("[!] webgl data vendor/renderer do not match the requested pair")

    gpus.append(
        {
            "preset_id": pid,
            "os": args.os,
            "vendor": args.vendor,
            "renderer": args.renderer,
            "webgl_data": data,
            "preset": preset_stub(args.os, args.vendor, args.renderer, args.cores, args.ua, screen),
        }
    )
    GPUS_JSON.write_text(json.dumps(pack, indent=2) + "\n")
    print(f"[+] {pid}  ({len(data['webGl:supportedExtensions'])} webgl1 extensions, source: {source})")


if __name__ == "__main__":
    main()
