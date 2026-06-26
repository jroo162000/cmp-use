"""
Lazy import helpers for cmp-use tools.

Importing the tool registry imports every tool module, and several tools pull in
heavy third-party libraries (cv2, mediapipe, PIL, pyautogui, ...). Loading those at
module top made `import cmpuse.tools` take 60-135s, which stalled the AVA worker's
startup. These helpers let a tool reference a heavy module / instance by name and
only actually import / construct it the first time it's used (i.e. when the tool
runs), so the registry imports in well under a second.

Usage in a tool module:
    from .._lazyimport import lazy_module, LazyInstance
    cv2 = lazy_module("cv2")            # use cv2.foo(...) exactly as before
    np  = lazy_module("numpy")
    manager = LazyInstance(SomeClass)   # use manager.method(...) exactly as before
"""
import importlib


class _LazyModule:
    """Proxy that imports the real module on first attribute access."""
    __slots__ = ("_name", "_mod")

    def __init__(self, name):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_mod", None)

    def _load(self):
        m = object.__getattribute__(self, "_mod")
        if m is None:
            m = importlib.import_module(object.__getattribute__(self, "_name"))
            object.__setattr__(self, "_mod", m)
        return m

    def __getattr__(self, attr):
        return getattr(self._load(), attr)

    def __setattr__(self, attr, value):
        # Allows module-level config like `pyautogui.FAILSAFE = False` to work
        # (it loads the real module and sets the attribute there).
        setattr(self._load(), attr, value)


def lazy_module(name):
    """Return a proxy for a module that imports lazily on first use."""
    return _LazyModule(name)


class LazyInstance:
    """Proxy that constructs the real object via `factory()` on first use.

    Lets a module keep a module-level singleton (e.g. `manager = LazyInstance(Manager)`)
    without running the (heavy) constructor at import time.
    """

    def __init__(self, factory):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_obj", None)

    def _ensure(self):
        o = object.__getattribute__(self, "_obj")
        if o is None:
            o = object.__getattribute__(self, "_factory")()
            object.__setattr__(self, "_obj", o)
        return o

    def __getattr__(self, name):
        return getattr(self._ensure(), name)

    def __setattr__(self, name, value):
        setattr(self._ensure(), name, value)
