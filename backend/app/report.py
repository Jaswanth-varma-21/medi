"""Assembles the A-E report draft as one self-contained, printable HTML page. Everything is HTML-escaped."""
from datetime import datetime
from html import escape as e

CSS = """
body{font:15px/1.55 system-ui,sans-serif;color:#12202b;max-width:760px;margin:32px auto;padding:0 20px}
h1{font:600 24px Georgia,serif;margin:0}h2{font-size:16px;margin:26px 0 8px;border-bottom:1px solid #ccd6db;padding-bottom:4px}
.stamp{display:inline-block;border:2px solid #b06f0c;color:#b06f0c;border-radius:6px;padding:2px 8px;font-weight:700;font-size:12px}
dl{display:grid;grid-template-columns:140px 1fr;gap:4px 12px;margin:0}dt{color:#4b5c68}dd{margin:0}
.warn{background:#fbf1de;padding:6px 10px;border-radius:6px}.src{font-size:12px;font-weight:600;color:#24609e}
.src.r{color:#2b7a57}small,.muted{color:#4b5c68}li{margin-bottom:4px}
@media print{body{margin:0}}
"""


def _facts(rows):
    return "<dl>" + "".join(f"<dt>{e(k)}</dt><dd>{e(str(v))}</dd>" for k, v in rows) + "</dl>"


def build_html(image, report, report_source=""):
    image = image or {}
    exam, quality, an = image.get("exam"), image.get("quality"), image.get("analysis")
    obs = (an or {}).get("observations", [])
    parts = []

    # A
    if exam:
        rows = [("Image type", exam.get("label")), ("Region", exam.get("region")), ("View", exam.get("view") or "Not stated"),
                ("File", f"{exam.get('format')}, {exam.get('width')}x{exam.get('height')} px, {exam.get('size_kb')} KB")]
        a = _facts(rows)
        for w in (quality or {}).get("warnings", []):
            a += f'<p class="warn">{e(w["message"])}</p>'
        for n in (quality or {}).get("notes", []):
            a += f'<p class="muted">{e(n)}</p>'
    else:
        a = '<p class="muted">No image was supplied.</p>'
    parts.append(("A. Examination information", a))

    # B
    if not an:
        b = '<p class="muted">No image analysis was run.</p>'
    elif an.get("status") == "no_model":
        b = f'<p class="warn">{e(an.get("message", ""))}</p>'
    elif not obs:
        b = "<p>The model did not report any of its supported findings.</p>"
    else:
        b = "<ul>" + "".join(
            f"<li><b>{e(o['finding'])}</b>, {e(o['location'])}. Model score {o['score']} (flag threshold {o['threshold']})"
            f"{' - flagged' if o.get('flagged') else ' - not flagged'}."
            f"{('<br><small>' + e(o['uncertainty']) + '</small>') if o.get('uncertainty') else ''}</li>"
            for o in obs) + "</ul>"
    parts.append(("B. AI-generated observations", b))

    # C
    c = ""
    for f in image.get("explanations", []):
        v = f["verification"]
        c += (f'<p><span class="src">From the image model</span><br><b>{e(f["title"])}.</b> {e(f["explanation"]["text"])}<br>'
              f'<small>Checked against evidence: {e(v["status"])} (confidence {e(v["confidence"])}).</small></p>')
    seen = set()
    for f in (report or {}).get("findings", []):
        key = (f["title"], f["status"])
        if key in seen:
            continue
        seen.add(key)
        c += (f'<p><span class="src r">From the written report</span><br><b>{e(f["title"])}.</b> {e(f["explanation"]["text"])}<br>'
              f'<small>Checked against evidence: {e(f["verification"]["status"])}.</small></p>')
    parts.append(("C. Plain-language explanation", c or '<p class="muted">Nothing to explain: no supported observations.</p>'))

    # D
    model = (an or {}).get("model")
    rows = [("Model", f"{model['id']} v{model['version']}" if model else "None installed"),
            ("Processing", "Image checked, model run" if an and an.get("status") == "ok" else ("Image checked, model not run" if an else "Not started")),
            ("Written report", report_source or ("Pasted text" if report else "Not supplied"))]
    d = _facts(rows)
    if an:
        d += "<ul>" + "".join(f"<li>{e(x)}</li>" for x in an.get("limitations", [])) + "</ul>"
    if report:
        d += f'<p class="muted">Report knowledge base: {e(report.get("knowledge_base", ""))}.</p>'
    parts.append(("D. Evidence and traceability", d))

    # E
    parts.append(("E. Review status", _facts([("Report status", "AI-generated draft"), ("Clinician review", "Pending"),
                                              ("Final report", "Not issued. Only after authorized review.")])))

    body = "".join(f"<h2>{e(t)}</h2>{h}" for t, h in parts)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>MedTruth AI report draft</title>'
            f"<style>{CSS}</style></head><body><h1>MedTruth AI report</h1>"
            f'<p><span class="stamp">AI-generated draft</span> <span class="muted">Generated {stamp}. For clinician review. '
            f"Not a diagnosis.</span></p>{body}</body></html>")
