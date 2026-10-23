"""Chest X-ray adapter for TorchXRayVision (open-source, pretrained on public chest X-ray datasets).

Install:  pip install -r requirements-models.txt   (first run downloads the weights, needs internet)
Enable:   MEDTRUTH_CHEST_MODEL=xrv in backend/.env

NOT validated by the MedTruth authors. Its scores are not calibrated probabilities. Test it on labelled,
de-identified images from your own setting before anyone relies on it.
"""
import math

import numpy as np

from ..vision import register_model

WEIGHTS = "densenet121-res224-all"


def load():
    import torch
    import torchvision
    import torchxrayvision as xrv

    model = xrv.models.DenseNet(weights=WEIGHTS).eval()
    prep = torchvision.transforms.Compose([xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(224)])
    op = getattr(model, "op_threshs", None)
    names = [n for n in model.pathologies if n]

    def run(gray):
        img = xrv.datasets.normalize(np.asarray(gray, dtype=np.float32), 255)[None, ...]
        img = prep(img)
        with torch.no_grad():
            out = model(torch.from_numpy(img)[None, ...])[0].numpy()
        found = []
        for i, name in enumerate(model.pathologies):
            if not name:
                continue
            thr = 0.5
            if op is not None:
                t = float(op[i])
                thr = 0.5 if math.isnan(t) else t
            found.append({"finding": name.replace("_", " "), "location": None, "score": float(out[i]), "threshold": thr})
        return found

    register_model("chest", run, model_id=f"torchxrayvision/{WEIGHTS}", version=getattr(xrv, "__version__", "unknown"), findings=names)
