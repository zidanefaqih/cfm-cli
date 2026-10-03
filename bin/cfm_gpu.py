"""Extra real-GPU WebGL identities shared by cfox, cfm and cfox-verify.

Camoufox's bundled preset pool only covers a handful of renderer strings, so
profiles on the same OS repeat the same GPU. This module adds more identities
under the same rule Camoufox itself uses: a GPU is usable only if Firefox has
actually been recorded reporting it on that OS (fpgen's pinned model). The
data lives in extras/gpus.json.

Why model names like GTX 1050 / RTX 3050 / RTX 4060 are NOT added: Gecko's
SanitizeRenderer collapses every one of those to a representative string
("GeForce GTX 980", "GeForce GTX 480") before a page sees it, so a real
Firefox never reports them. Naming one is a spoofing tell, not variety.

Drop-in standalone: this file sits next to the scripts and is imported from
the same directory, so keep it with cfox/cfm/cfox-verify when copying them.
"""
import json
import os
import pathlib


def _candidates():
    """Where to look for gpus.json, most specific first."""
    env = os.environ.get("CAMOUFOX_GPUS")
    if env:
        yield pathlib.Path(env)
    here = pathlib.Path(__file__).resolve().parent
    yield here / "gpus.json"
    yield here.parent / "extras" / "gpus.json"          # repo clone: bin/../extras
    yield pathlib.Path.home() / ".local" / "share" / "cfm-cli" / "gpus.json"


def load_extra_gpus():
    """Return (gpus, path). gpus is [] when no pack is found or it is invalid."""
    for path in _candidates():
        try:
            if path.is_file():
                data = json.loads(path.read_text())
                gpus = data.get("gpus") if isinstance(data, dict) else data
                if isinstance(gpus, list):
                    return gpus, path
        except Exception:
            continue
    return [], None


def extra_presets(os_name):
    """Extra GPU entries for one OS, in pack order."""
    gpus, _ = load_extra_gpus()
    return [g for g in gpus if isinstance(g, dict) and g.get("os") == os_name]


def install_sample_webgl_patch():
    """Make Camoufox serve the generated data for extra GPUs.

    Camoufox resolves a preset's (vendor, renderer) against its bundled
    webgl_data.db and raises
        ValueError: No WebGL data found for vendor ... and renderer ...
    when the pair is absent. Extra GPUs are not in that database, so their
    recorded data is returned here instead. Safe to call more than once.
    """
    gpus, _ = load_extra_gpus()
    table = {
        (g.get("vendor"), g.get("renderer")): g.get("webgl_data")
        for g in gpus
        if isinstance(g, dict) and g.get("webgl_data")
    }
    if not table:
        return 0

    import camoufox.utils as _utils
    try:
        import camoufox.fingerprints as _fp
    except Exception:
        _fp = None

    def _wrap(original):
        def sample_webgl(target_os, vendor=None, renderer=None):
            if vendor and renderer and (vendor, renderer) in table:
                return dict(table[(vendor, renderer)])
            return original(target_os, vendor, renderer)

        sample_webgl._cfm_extra = True
        return sample_webgl

    if not getattr(_utils.sample_webgl, "_cfm_extra", False):
        _utils.sample_webgl = _wrap(_utils.sample_webgl)
    if _fp is not None and hasattr(_fp, "sample_webgl") and not getattr(_fp.sample_webgl, "_cfm_extra", False):
        _fp.sample_webgl = _wrap(_fp.sample_webgl)
    return len(table)
