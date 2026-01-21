__all__ = ["__version__", "__app_version__"]

__version__ = "0.1.0"

try:
    from scale_vision.versioning import app_version

    __app_version__, _ = app_version()
except Exception:
    __app_version__ = __version__
