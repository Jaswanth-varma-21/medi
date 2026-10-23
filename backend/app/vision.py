"""Step 2: medical-image AI models, one per specialty.

No model ships with this project. Each specialty needs its own suitable pretrained model and its own
validation before it is trusted. Until a model is registered for a specialty, the API says so plainly and
returns NO findings: it never invents image findings.

To plug one in (example for chest, using any model you have validated):

    from app.vision import register_model
    def run_chest(gray_image):          # PIL 'L' image in, list of dicts out
        return [{"finding": "Pleural effusion", "location": "Right lower zone", "score": 0.81, "threshold": 0.5}]
    register_model("chest", run_chest, model_id="my-chest-model", version="1.0",
                   findings=["Pleural effusion", "Cardiomegaly"])
"""
MODALITIES = {
    "chest": {"label": "Chest X-ray", "region": "Chest (lungs, heart, pleura)", "scope": "selected lung and cardiac findings"},
    "bone": {"label": "Bone X-ray", "region": "Bone and joint", "scope": "selected bone and joint abnormalities"},
    "spine": {"label": "Spine X-ray", "region": "Spine", "scope": "supported spinal findings"},
    "dental": {"label": "Dental X-ray", "region": "Teeth and jaw", "scope": "selected dental abnormalities"},
}
_MODELS = {}


def register_model(modality, fn, model_id, version, findings):
    if modality not in MODALITIES:
        raise KeyError(modality)
    _MODELS[modality] = {"fn": fn, "id": model_id, "version": version, "findings": list(findings)}


def run_model(modality, gray, quality):
    info = MODALITIES[modality]
    entry = _MODELS.get(modality)
    limits = [
        "AI observations are estimates, not a diagnosis.",
        "Scores are model outputs and are not calibrated probabilities unless the model's validation says so.",
    ]
    if entry is None:
        return {
            "status": "no_model",
            "model": None,
            "observations": [],
            "message": f"No validated model is installed for {info['label'].lower()}. No image findings were generated.",
            "limitations": limits,
        }
    raw = entry["fn"](gray)
    uncertain_input = quality["status"] != "ok"
    obs = []
    for r in raw:
        score = float(r["score"])
        thr = float(r.get("threshold", 0.5))
        obs.append(
            {
                "finding": r["finding"],
                "location": r.get("location") or "Not localised by the model",
                "score": round(score, 3),
                "threshold": thr,
                "flagged": score >= thr,
                "uncertainty": "Image quality warnings apply; treat this score with extra caution." if uncertain_input else None,
            }
        )
    return {
        "status": "ok",
        "model": {"id": entry["id"], "version": entry["version"], "findings_covered": entry["findings"]},
        "observations": obs,
        "message": None,
        "limitations": limits + [f"Only these findings are covered: {', '.join(entry['findings'])}."],
    }
