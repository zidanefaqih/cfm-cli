# WebGL `readPixels` hands back the physical GPU's pixels (canvas noise does not cover it)

## Who's asking

I run a small Camoufox-based profile setup on one Linux box — a handful of
long-lived profiles, each with a pinned config. Camoufox does the hard part and
the pinned-config replay works well, so this is a report, not a request to change
a default.

Measured on Camoufox 0.5.6 (Python wrapper) with browser build 152.0.4-beta.30
on Pop!_OS 24.04.

## Summary

WebGL *identity* is spoofed correctly. WebGL *output* is not. `gl.readPixels()`
returns the framebuffer produced by the physical GPU, byte for byte, so every
profile on a machine — and the machine's everyday browser — produces the same
WebGL render fingerprint. `canvas:seed` / `fonts:spacing_seed` do not reach this
path, and neither does the sanitizer.

This is the render *output*, not the parameters. Parameters are fine: all 74
`getParameter` values I can read match the spoof table exactly
(`MAX_COMBINED_TEXTURE_IMAGE_UNITS` = 192 from the preset vs 64 from the host).

## Reproduction

```js
const c = document.createElement('canvas');          // 300x150
const gl = c.getContext('webgl');
// ... compile a fragment shader with several sin/cos iterations,
//     drawArrays(TRIANGLE_STRIP, 0, 3) ...
const px = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight,
              gl.RGBA, gl.UNSIGNED_BYTE, px);
// hash px
```

Measured on this machine (Pop!_OS 24.04, GeForce GTX 1660 SUPER, driver 595.84),
`djb2` over the 180000 bytes:

| Runner | Renderer the page sees | Hash of `readPixels` |
| --- | --- | --- |
| Camoufox, profile A (preset spoofing a GTX 980) | `NVIDIA GeForce GTX 980, or similar` | `3213959167` |
| Camoufox, profile B (different preset, same spoofed GPU) | `NVIDIA GeForce GTX 980, or similar` | `3213959167` |
| Real Chrome on the host GPU | `...GTX 1660 SUPER/PCIe/SSE2...` | `3213959167` |
| Real Chrome, `--disable-gpu` (SwiftShader) | `...SwiftShader Device...` | `3529713129` |

The SwiftShader row is the control: the probe is sensitive to the render backend.
Camoufox matches the **hardware** row, not a software fallback — so the frame is
genuinely drawn by the physical GPU and handed back unchanged. Alpha is included,
noise is absent, and `canvas.toDataURL()` and `drawImage(webglCanvas)` ->
`getImageData()` behave the same way.

## Why it matters

`readPixels` is one of the standard WebGL fingerprinting paths, not an exotic
one. One concrete, verified example: the fingerprinting library served by
pixelscan.net computes its displayed "WebGL Hash" as
`MD5(pixels.join(''))` from exactly this call, on a 300x150 canvas. Replicating
that routine locally reproduces the site's reported value byte for byte:

- Camoufox profile: `MD5(...)` = `a456bf40dcd7c61cff770ba942109b39`
- Same value in real Chrome on the host, and in the host's everyday browser

So the rendered pixels tie every profile on the machine together, and tie them
to the operator's own browser, regardless of which GPU the preset claims.

I also tried to fix it from the JS side (wrapping `readPixels` on
`WebGLRenderingContext` / `WebGL2RenderingContext` via an init script, +-1 LSB
per-profile noise). It works on ordinary pages but is not reliable: a page that
renders inside an iframe created with `src="javascript:..."` runs synchronously
when the element is attached, before any document-start injection reaches it, and
the value escapes again. That is what pushed me to file this.

## Suggested fix

Noise the readback where the 2D canvas path is already handled, in the WebGL
read path (`ClientWebGLContext::ReadPixels` / `webgl::ReadPixels`), so it applies
to every frame and worker and cannot be raced from JS. Note that `canvas:seed`
was removed entirely in #787 ("nothing has read it since #528 removed canvas
noise"), so this is not about wiring up an existing seed — it would be a new
seeded noise source at the C++ readback path. Issue #721's original report of
an unconsumed `canvas:seed` is what led to that removal; the WebGL readback gap
reported here is the piece that removal left behind.

Happy to test a build or provide the full reproducer (including the shader and
the exact hashing) if that helps. I am not claiming this is easy — just that the
leak is real, measurable, and frame-independent.
