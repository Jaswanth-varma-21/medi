"""Optional image models. Set MEDTRUTH_CHEST_MODEL=xrv to load the chest model at start-up."""
import logging
import os

log = logging.getLogger("medtruth")


def autoload():
    if os.getenv("MEDTRUTH_CHEST_MODEL", "").lower() == "xrv":
        try:
            from .chest_xrv import load

            load()
            log.info("Chest model loaded: TorchXRayVision")
        except Exception as err:  # missing package, no weights, no network on first run
            log.warning("Chest model not loaded (%s). The app will report 'no model installed'.", err)
