"""Per-profile noise for the WebGL pixel readback path (AF-006).

Why this exists
---------------
Camoufox spoofs every WebGL *parameter* correctly, but it does not touch the
render itself: the frame is drawn by the physical GPU, and `gl.readPixels()`
returns that framebuffer byte-for-byte. `canvas.toDataURL()` and
`drawImage(webglCanvas)` -> `getImageData()` behave the same way. So every
profile on one machine produces identical WebGL render output, and it also
matches the machine's everyday browser. Any site that hashes the rendered
pixels (pixelscan.net demonstrably does -- it calls `readPixels` three times,
180000 bytes each) can link every profile together and back to the host.

This module closes that hole the same way Camoufox already handles 2D canvas:
a small deterministic perturbation applied on readback, seeded per profile.

Properties
----------
* Stable per profile -- the delta depends only on (seed, x, y), never on the
  read order, so two runs of the same profile return identical bytes.
* Different between profiles -- one random 32-bit seed per profile.
* Quiet -- +-1 LSB on a fraction of pixels, RGB only, alpha untouched.
* Non-destructive -- only the returned ArrayBufferView is modified, never the
  framebuffer, so reading the same region twice gives the same answer.

Limits (do not oversell this)
-----------------------------
* Covers `readPixels` only. `toDataURL()` / `toBlob()` on a WebGL canvas and
  `drawImage(webglCanvas)` into a 2D canvas are NOT covered yet.
* It is a JavaScript patch living in the page's main world. Camoufox itself
  patches at the C++ level and injects no page JS, so this is the only
  JS-level modification of the page. `Function.prototype.toString` is proxied
  so the wrapper still reads as `[native code]`.
* A pixel-perfect uniformity check (clear to an exact colour, read it back,
  expect an exact match) would notice the noise. That is the cost of not
  leaking the physical GPU.

Drop-in standalone: sits next to cfox/cfm and is imported from the same
directory, so keep it with them when copying the scripts.
"""
import os
import pathlib
import secrets

SEED_FILE = ".cfm-readpixels-seed"

# --- the injected script -----------------------------------------------------
# __CFM_SEED__ is replaced with an unsigned 32-bit integer.
_SCRIPT = r"""
(() => {
  "use strict";
  const SEED = __CFM_SEED__;

  // Cost: one tiny hash per pixel. Cheap enough for the 300x150 (45000 pixel)
  // readback that fingerprinting scripts use, and only paid on readback.
  function noiseAt(x, y, out) {
    let s = (SEED ^ Math.imul(x, 0x9e3779b1) ^ Math.imul(y, 0x85ebca6b)) | 0;
    s ^= s >>> 15; s = Math.imul(s, 0x2c1b3c6d);
    s ^= s >>> 12; s = Math.imul(s, 0x297a2d39);
    s ^= s >>> 15;
    // ~1/4 of pixels get +-1; the rest are left alone.
    if ((s & 3) !== 0) { out[0] = 0; out[1] = 0; out[2] = 0; return; }
    out[0] = ((s >>> 2) & 1) ? 1 : -1;
    out[1] = ((s >>> 3) & 1) ? 1 : -1;
    out[2] = ((s >>> 4) & 1) ? 1 : -1;
  }

  const _toString = Function.prototype.toString;
  const _fake = new Map();
  // Idempotency marker kept in a closure, never as a property on the wrapper:
  // own properties on the patched function would be visible to the page.
  const _done = new WeakSet();

  function wrap(proto) {
    if (!proto) return;
    const orig = proto.readPixels;
    if (typeof orig !== "function" || _done.has(orig)) return;
    _done.add(orig);

    const patched = function readPixels(x, y, w, h, format, type, pixels) {
      const rv = orig.apply(this, arguments);
      // Only the JS-readback form. The PIXEL_PACK_BUFFER form (offset, no
      // ArrayBufferView) never reaches JS, so there is nothing to perturb.
      if (!pixels || typeof pixels.length !== "number" || !pixels.buffer) return rv;
      if (type !== 5121) return rv;                  // UNSIGNED_BYTE only
      if (format !== 6408 && format !== 6407) return rv;  // RGBA | RGB
      try {
        const ch = (format === 6408) ? 4 : 3;
        const len = Math.min(pixels.length, w * h * ch);
        const d = [0, 0, 0];
        for (let i = 0, p = 0; i < len; i += ch, p++) {
          noiseAt(x + (p % w), y + ((p / w) | 0), d);
          if (d[0] | d[1] | d[2]) {
            for (let c = 0; c < 3; c++) {
              const v = pixels[i + c] + d[c];
              if (v >= 0 && v <= 255 && d[c]) pixels[i + c] = v;
            }
          }
        }
      } catch (e) { /* never break the page over noise */ }
      return rv;
    };

    // Mirror the native shape exactly -- name and arity are both readable.
    try {
      const src = _toString.call(orig);
      Object.defineProperty(patched, "name", { value: orig.name });
      Object.defineProperty(patched, "length", { value: orig.length });
      _fake.set(patched, /\[native code\]/.test(src)
        ? "function " + orig.name + "() {\n    [native code]\n}"
        : src);
    } catch (e) {}

    try { proto.readPixels = patched; } catch (e) {}
  }

  wrap(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  wrap(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);

  // Keep the wrapper looking native. A Proxy (not a plain function) so that
  // typeof/name/length and the `toString` identity itself stay consistent.
  try {
    Function.prototype.toString = new Proxy(_toString, {
      apply(target, self, args) {
        const f = _fake.get(self);
        return (f !== undefined) ? f : Reflect.apply(target, self, args);
      },
    });
  } catch (e) {}
})();
"""


def seed_file(profile_dir):
    """Path of the per-profile seed file."""
    return pathlib.Path(profile_dir) / SEED_FILE


def ensure_seed(profile_dir):
    """Return the profile's 32-bit noise seed, creating it on first use.

    One random seed per profile, persisted next to the profile so that the
    same profile always produces the same readback bytes.
    """
    p = seed_file(profile_dir)
    try:
        raw = p.read_text().strip()
        if raw:
            return int(raw, 16) & 0xFFFFFFFF
    except Exception:
        pass
    value = secrets.randbits(32)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("%08x\n" % value)
        os.chmod(p, 0o600)
    except Exception:
        pass
    return value


def script(seed):
    """The init script for a given numeric seed."""
    return _SCRIPT.replace("__CFM_SEED__", "%d" % (int(seed) & 0xFFFFFFFF))


def install(ctx, seed):
    """Attach the readPixels noise to a (persistent) browser context.

    Must run before the first navigation, otherwise already-open documents
    keep the unpatched prototype.
    """
    ctx.add_init_script(script(seed))
    return ctx


def enabled():
    """Escape hatch: CFM_READPIXELS_NOISE=0 disables the patch."""
    return os.environ.get("CFM_READPIXELS_NOISE", "1").strip() not in ("0", "off", "false", "no")
