import { useEffect, useMemo, useRef, useState } from "react";

const STATUS_LABEL = {
  present: "Reported",
  absent: "Reported as not seen",
  uncertain: "Uncertain wording",
};
const CHECK_LABEL = {
  verified: "Checked against evidence",
  partial: "Partly supported",
  flagged: "Flagged: needs review",
  no_evidence: "No evidence found",
};
const CLAIM_LABEL = { supported: "Supported", partial: "Partly supported", unsupported: "Not supported" };
const IMAGE_STATUS_LABEL = "Model estimate";
const URGENCY_TEXT = {
  prompt: "Doctors usually treat this as time-sensitive. Contact the doctor who ordered this X-ray.",
  discuss: "Worth discussing with your doctor.",
};

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const MODALITIES = [
  { id: "chest", label: "Chest", scope: "Selected lung and cardiac findings" },
  { id: "bone", label: "Bone", scope: "Selected bone and joint abnormalities" },
  { id: "spine", label: "Spine", scope: "Supported spinal findings" },
  { id: "dental", label: "Dental", scope: "Selected dental abnormalities" },
];
const VIEWS = ["", "PA", "AP", "Lateral", "Oblique", "Panoramic", "Bitewing", "Periapical"];

function groupFindings(findings) {
  const map = new Map();
  for (const f of findings) {
    const key = `${f.title}|${f.status}`;
    if (!map.has(key)) map.set(key, { key, first: f, sentenceIndexes: [] });
    map.get(key).sentenceIndexes.push(f.sentence_index);
  }
  return [...map.values()];
}

function ReportPane({ text, result, activeGroup }) {
  const byIndex = useMemo(() => {
    const m = new Map();
    for (const f of result.findings) if (!m.has(f.sentence_index)) m.set(f.sentence_index, f);
    return m;
  }, [result]);
  const parts = [];
  let cursor = 0;
  for (const s of result.sentences) {
    if (s.start > cursor) parts.push(text.slice(cursor, s.start));
    const f = byIndex.get(s.index);
    const active = activeGroup && activeGroup.sentenceIndexes.includes(s.index);
    const cls = ["sentence", f ? `s-${f.status}` : "s-none", active ? "is-active" : ""].join(" ");
    parts.push(
      <mark key={s.index} className={cls} title={f ? STATUS_LABEL[f.status] : "Not interpreted by MedTruth"}>
        {text.slice(s.start, s.end)}
      </mark>
    );
    cursor = s.end;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <p className="report-text">{parts}</p>;
}

function FindingRow({ group, active, onSelect }) {
  const f = group.first;
  const v = f.verification;
  return (
    <li className={`finding st-${f.status} ${active ? "is-active" : ""}`}>
      <button className="finding-head" onClick={onSelect} aria-pressed={active}>
        <span className="finding-title">{f.title}</span>
        <span className={`chip chip-${f.status}`}>{f.source === "image" ? `${IMAGE_STATUS_LABEL} ${f.model_score}` : STATUS_LABEL[f.status]}</span>
        <span className={`chip chip-check-${v.status}`}>{CHECK_LABEL[v.status]}</span>
      </button>
      <p className="explanation">{f.explanation.text}</p>
      {f.status !== "absent" && URGENCY_TEXT[f.urgency] && (
        <p className={`urgency urgency-${f.urgency}`}>{URGENCY_TEXT[f.urgency]}</p>
      )}
      <details className="trail">
        <summary>
          Evidence trail
          {group.sentenceIndexes.length > 1 ? ` (mentioned in ${group.sentenceIndexes.length} sentences)` : ""}
        </summary>
        <p className="trail-label">{f.source === "image" ? "From the image model" : "From your report"}</p>
        <blockquote>{f.sentence}</blockquote>
        <p className="trail-label">Evidence retrieved</p>
        <ul className="evidence">
          {f.evidence.map((e) => (
            <li key={e.entry_id}>
              <strong>{e.title}</strong> <span className="score">match {e.score}</span>
              <br />
              {e.summary}
            </li>
          ))}
        </ul>
        <p className="source-note">{f.evidence[0] ? f.evidence[0].source : ""}</p>
        <p className="trail-label">Each claim, checked</p>
        <ul className="claims">
          {v.claims.map((c, i) => (
            <li key={i} className={`claim claim-${c.label}`}>
              <span className="claim-label">{CLAIM_LABEL[c.label]}</span> {c.text}
              {c.from.length > 0 && <span className="claim-from"> (found in: {c.from.join(", ")})</span>}
              {c.reasons.length > 0 && c.label !== "supported" && (
                <span className="claim-reason"> {c.reasons.join("; ")}.</span>
              )}
            </li>
          ))}
        </ul>
        <p className="meta">
          Confidence: {v.confidence}. Explanation written by: {f.explanation.method}.
        </p>
      </details>
    </li>
  );
}

function Steps({ steps }) {
  return (
    <ol className="steps" aria-label="Progress">
      {steps.map((s, i) => (
        <li key={s.label} className={`step step-${s.state}`} aria-current={s.state === "now" ? "step" : undefined}>
          <span className="step-dot">{s.state === "done" ? "✓" : i + 1}</span>
          <span className="step-text">
            <strong>{s.label}</strong>
            <small>{s.note}</small>
          </span>
        </li>
      ))}
    </ol>
  );
}

function Section({ id, title, children }) {
  return (
    <section className="sheet-section" aria-labelledby={`sec-${id}`}>
      <h3 id={`sec-${id}`}>
        <span className="sec-id">{id}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function DraftReport({ img, report, reportFile, onDownload, onPrint, busy }) {
  const exam = img && img.exam;
  const q = img && img.quality;
  const an = img && img.analysis;
  const obs = (an && an.observations) || [];
  return (
    <article className="sheet" aria-label="Generated report draft">
      <header className="sheet-head">
        <div>
          <h2>MedTruth AI report</h2>
          <p>Illustrative draft structure. Not an actual clinical result.</p>
        </div>
        <span className="stamp">AI-generated draft</span>
      </header>
      <div className="sheet-tools">
        <button type="button" className="secondary" disabled={(!img && !report) || busy} onClick={onDownload}>Download draft</button>
        <button type="button" className="secondary" disabled={!img && !report} onClick={onPrint}>Print</button>
      </div>

      <Section id="A" title="Examination information">
        {exam ? (
          <dl className="facts">
            <div><dt>Image type</dt><dd>{exam.label}</dd></div>
            <div><dt>Region</dt><dd>{exam.region}</dd></div>
            <div><dt>View</dt><dd>{exam.view || "Not stated"}</dd></div>
            <div><dt>File</dt><dd>{exam.format}, {exam.width}×{exam.height}px, {exam.size_kb} KB</dd></div>
          </dl>
        ) : (
          <p className="placeholder">Upload an image to fill this in.</p>
        )}
        {q && (q.warnings.length === 0 ? (
          <p className="note note-ok">No image-quality warnings.</p>
        ) : (
          <ul className="warnlist">
            {q.warnings.map((w) => <li key={w.code}>{w.message}</li>)}
          </ul>
        ))}
      </Section>

      <Section id="B" title="AI-generated observations">
        {!an && <p className="placeholder">Model observations appear here, labelled with their score.</p>}
        {an && an.status === "no_model" && <p className="note note-warn">{an.message}</p>}
        {an && an.status === "ok" && obs.length === 0 && <p className="note">The model did not report any of its supported findings.</p>}
        {obs.length > 0 && (
          <ul className="obs">
            {obs.map((o, i) => (
              <li key={i} className={o.flagged ? "obs-flag" : ""}>
                <div className="obs-main">
                  <strong>{o.finding}</strong>
                  <span>{o.location}</span>
                </div>
                <div className="meter" role="img" aria-label={`Model score ${o.score}, threshold ${o.threshold}`}>
                  <span className="meter-fill" style={{ width: `${Math.round(o.score * 100)}%` }} />
                  <span className="meter-thr" style={{ left: `${Math.round(o.threshold * 100)}%` }} />
                </div>
                <small>Model score {o.score} (flag threshold {o.threshold})</small>
                {o.uncertainty && <small className="unc">{o.uncertainty}</small>}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="C" title="Plain-language explanation">
        {(!img || !img.explanations || img.explanations.length === 0) && !report && <p className="placeholder">Only supported observations are explained here. Nothing is added.</p>}
        {img && img.explanations && img.explanations.length > 0 && (
          <>
            <span className="src src-model">From the image model</span>
            <ul className="findings">
              {img.explanations.map((f) => (
                <FindingRow key={f.id} group={{ key: `img-${f.id}`, first: f, sentenceIndexes: [] }} active={false} onSelect={() => {}} />
              ))}
            </ul>
          </>
        )}
        {report && report.findings.length > 0 && <span className="src src-report">From the written report</span>}
        {report && report.findings.length > 0 && groupFindings(report.findings).map((g) => (
          <p key={g.key} className="plain">
            <strong>{g.first.title}: </strong>{g.first.explanation.text}
          </p>
        ))}
        {report && report.findings.length === 0 && <p className="note">No findings from the knowledge base were recognised in the written report.</p>}
      </Section>

      <Section id="D" title="Evidence and traceability">
        <dl className="facts">
          <div><dt>Model</dt><dd>{an && an.model ? `${an.model.id} v${an.model.version}` : "None installed"}</dd></div>
          <div><dt>Processing</dt><dd>{!img ? "Not started" : an.status === "ok" ? "Image checked, model run" : "Image checked, model not run"}</dd></div>
          <div><dt>Written report</dt><dd>{report ? (reportFile || "Pasted text") : "Not supplied"}</dd></div>
        </dl>
        {an && <ul className="limits">{an.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      </Section>

      <Section id="E" title="Review status">
        <ol className="review">
          <li className="rv-now"><strong>AI-generated draft</strong><span>Produced automatically</span></li>
          <li><strong>Clinician review</strong><span>Pending</span></li>
          <li><strong>Final report</strong><span>Not issued. Only after authorized review.</span></li>
        </ol>
      </Section>
    </article>
  );
}

export default function App() {
  const [modality, setModality] = useState("chest");
  const [view, setView] = useState("");
  const [image, setImage] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [previewFailed, setPreviewFailed] = useState(false);
  const [imgResult, setImgResult] = useState(null);
  const [drag, setDrag] = useState(false);

  const [text, setText] = useState("");
  const [samples, setSamples] = useState([]);
  const [health, setHealth] = useState(null);
  const [result, setResult] = useState(null);
  const [analyzed, setAnalyzed] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeKey, setActiveKey] = useState(null);
  const [fileName, setFileName] = useState("");
  const [reading, setReading] = useState(false);
  const fileInput = useRef(null);
  const imageInput = useRef(null);

  useEffect(() => {
    api("/api/samples").then(setSamples).catch(() => {});
    api("/api/health").then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);
  useEffect(() => () => imageUrl && URL.revokeObjectURL(imageUrl), [imageUrl]);

  function chooseImage(file) {
    if (!file) return;
    setError("");
    if (file.size > MAX_IMAGE_BYTES) return setError("That image is larger than 15 MB.");
    setImage(file);
    setImgResult(null);
    setPreviewFailed(false);
    setImageUrl(URL.createObjectURL(file));
  }

  async function onFileChosen(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    if (file.size > MAX_FILE_BYTES) return setError("That file is larger than 5 MB. Please choose a smaller report file.");
    setReading(true);
    try {
      let content;
      if (/\.(txt|text|md)$/i.test(file.name)) {
        content = await file.text();
      } else {
        const res = await fetch("/api/extract?filename=" + encodeURIComponent(file.name), {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        });
        if (!res.ok) {
          let detail = "";
          try { detail = (await res.json()).detail; } catch { /* ignore */ }
          throw new Error(detail || `Could not read that file (${res.status}).`);
        }
        content = (await res.json()).text;
      }
      setText(content.slice(0, 20000));
      setFileName(file.name);
    } catch (err) {
      setError(err.message === "Failed to fetch" ? "Could not reach the MedTruth backend to read the file." : err.message);
    } finally {
      setReading(false);
    }
  }

  const groups = useMemo(() => (result ? groupFindings(result.findings) : []), [result]);
  const activeGroup = groups.find((g) => g.key === activeKey) || null;
  const canRun = (image || text.trim().length >= 10) && !loading;

  async function run() {
    setLoading(true);
    setError("");
    setActiveKey(null);
    const submitted = text.trim();
    const jobs = [];
    if (image) {
      jobs.push(
        api(`/api/image/analyze?modality=${modality}&view=${encodeURIComponent(view)}&filename=${encodeURIComponent(image.name)}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: image,
        }).then(setImgResult)
      );
    }
    if (submitted.length >= 10) {
      jobs.push(
        api("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ report_text: submitted, use_llm: true }),
        }).then((d) => { setResult(d); setAnalyzed(submitted); })
      );
    }
    const settled = await Promise.allSettled(jobs);
    const failed = settled.find((s) => s.status === "rejected");
    if (failed) {
      const m = failed.reason.message;
      setError(m.startsWith("Request failed") || m === "Failed to fetch" ? "Could not reach the MedTruth backend. Start it with: uvicorn app.main:app --port 8000" : m);
    }
    setLoading(false);
  }

  const q = imgResult && imgResult.quality;
  const steps = [
    { label: "Upload", note: image ? image.name : "X-ray image", state: image ? "done" : "now" },
    { label: "Image check", note: q ? (q.status === "ok" ? "Passed" : `${q.warnings.length} warning(s)`) : "Format and quality", state: q ? "done" : image ? "now" : "todo" },
    { label: "AI analysis", note: imgResult ? (imgResult.analysis.status === "ok" ? "Model run" : "No model installed") : "Selected findings", state: imgResult ? "done" : "todo" },
    { label: "Explain and verify", note: result ? `${result.summary.verified} of ${result.summary.findings} checked` : imgResult && imgResult.explanations.length ? `${imgResult.explanations.length} image finding(s) checked` : "Evidence and warnings", state: result || imgResult ? "done" : "todo" },
  ];
  async function downloadDraft() {
    setError("");
    try {
      const res = await fetch("/api/report/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imgResult, report: result, report_source: fileName }),
      });
      if (!res.ok) throw new Error(`Could not build the report (${res.status}).`);
      const url = URL.createObjectURL(new Blob([await res.text()], { type: "text/html" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "medtruth-report-draft.html";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message === "Failed to fetch" ? "Could not reach the MedTruth backend to build the report." : err.message);
    }
  }

  const specialty = MODALITIES.find((m) => m.id === modality);

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden="true"><i /><i /><i /></span>
          <div>
            <h1>MedTruth AI</h1>
            <p>Structured X-ray report drafts, with every statement traceable.</p>
          </div>
        </div>
        <p className="disclaimer" role="note">AI-generated draft for clinician review. It is not a diagnosis and does not replace your doctor or radiologist.</p>
      </header>

      <Steps steps={steps} />

      <main className="stage">
        <section className="viewer" aria-label="X-ray viewer">
          <div className="modal-tabs" role="tablist" aria-label="Image type">
            {MODALITIES.map((m) => (
              <button key={m.id} role="tab" aria-selected={modality === m.id} className={modality === m.id ? "on" : ""} onClick={() => { setModality(m.id); setImgResult(null); }}>
                {m.label}
              </button>
            ))}
          </div>
          <p className="scope">{specialty.scope}. Each specialty needs its own model and validation.</p>

          <div
            className={`film ${drag ? "drag" : ""} ${imageUrl ? "has-img" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); chooseImage(e.dataTransfer.files[0]); }}
          >
            {imageUrl && !previewFailed ? (
              <img src={imageUrl} alt="Uploaded X-ray" onError={() => setPreviewFailed(true)} />
            ) : (
              <div className="film-empty">
                <p>{previewFailed ? "Preview not available for this format. The file can still be analysed." : "Drop an X-ray image here"}</p>
                <small>PNG, JPEG, TIFF, BMP or WEBP, up to 15 MB</small>
              </div>
            )}
            {imageUrl && <span className="corner tl">{specialty.label}</span>}
            {imageUrl && view && <span className="corner tr">{view}</span>}
          </div>

          <input ref={imageInput} type="file" accept=".png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp" hidden onChange={(e) => { chooseImage(e.target.files[0]); e.target.value = ""; }} />
          <div className="viewer-actions">
            <button type="button" className="ghost" onClick={() => imageInput.current.click()}>{image ? "Replace image" : "Choose image"}</button>
            <label className="view-select">
              View
              <select value={view} onChange={(e) => setView(e.target.value)}>
                {VIEWS.map((v) => <option key={v} value={v}>{v || "Not stated"}</option>)}
              </select>
            </label>
          </div>

          {q && (
            <div className="quality">
              <div className="q-grid">
                <span>Contrast <b>{q.metrics.contrast}</b></span>
                <span>Sharpness <b>{q.metrics.sharpness}</b></span>
                <span>Brightness <b>{q.metrics.brightness}</b></span>
              </div>
              {q.notes && q.notes.map((n) => <p key={n} className="q-note">{n}</p>)}
              {q.warnings.length === 0 ? <p className="q-ok">Passed basic format and quality checks.</p> : (
                <ul>{q.warnings.map((w) => <li key={w.code}>{w.message}</li>)}</ul>
              )}
            </div>
          )}
        </section>

        <DraftReport img={imgResult} report={result} reportFile={fileName} onDownload={downloadDraft} onPrint={() => window.print()} busy={loading} />
      </main>

      <section className="written" aria-label="Written report">
        <div className="written-head">
          <div>
            <h2>Written report <small>optional</small></h2>
            <p>Paste or upload the radiologist's report. It is explained and verified separately, and never mixed into the model's image findings.</p>
          </div>
          {modality !== "chest" && <p className="note note-warn">The report knowledge base covers chest X-rays only. Explanations for other types will be limited.</p>}
        </div>

        {!result ? (
          <>
            <div className="samples">
              <span>Try a sample:</span>
              {samples.map((sm) => <button key={sm.id} className="link" onClick={() => setText(sm.text)}>{sm.title}</button>)}
            </div>
            <label htmlFor="report" className="sr-only">Report text</label>
            <textarea id="report" value={text} onChange={(e) => { setText(e.target.value); setFileName(""); }} placeholder="Paste the text of an X-ray report here" rows={8} />
            <div className="actions">
              <input ref={fileInput} type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp" onChange={onFileChosen} hidden />
              <button type="button" className="secondary" disabled={reading} onClick={() => fileInput.current.click()}>{reading ? "Reading file…" : "Choose report file"}</button>
              {fileName && <span className="hint-ok">Loaded: {fileName}</span>}
            </div>
          </>
        ) : (
          <div className="report-result">
            <div className="pane-report">
              <ReportPane text={analyzed} result={result} activeGroup={activeGroup} />
              <ul className="legend">
                <li><span className="swatch s-present" /> Reported finding</li>
                <li><span className="swatch s-absent" /> Reported as not seen</li>
                <li><span className="swatch s-uncertain" /> Uncertain wording</li>
                <li><span className="swatch s-none" /> Not interpreted</li>
              </ul>
              <button className="link" onClick={() => { setResult(null); setActiveKey(null); }}>Edit report</button>
            </div>
            <div className="pane-results">
              <p className="summary">
                {result.summary.findings === 0 ? "No findings from the knowledge base were recognised in this text." : `${result.summary.findings} finding${result.summary.findings === 1 ? "" : "s"} found, ${result.summary.verified} checked against evidence, ${result.summary.flagged} flagged.`}
                {result.summary.faithfulness !== null && ` Support score ${Math.round(result.summary.faithfulness * 100)}%.`}
              </p>
              <p className="meta">Explanations written {result.llm.enabled ? `with an LLM (${result.llm.model}) and then verified` : "from a built-in template (no LLM configured)"}.</p>
              <ul className="findings">
                {groups.map((g) => <FindingRow key={g.key} group={g} active={g.key === activeKey} onSelect={() => setActiveKey(g.key === activeKey ? null : g.key)} />)}
              </ul>
              <details className="agents">
                <summary>What each agent did</summary>
                <ol>{result.trace.map((t) => <li key={t.agent}><strong>{t.agent}.</strong> {t.output}</li>)}</ol>
                <p className="source-note">Knowledge base: {result.knowledge_base}</p>
              </details>
            </div>
          </div>
        )}
      </section>

      <div className="runbar">
        <div>
          {error && <p className="error" role="alert">{error}</p>}
          {!error && health && health.status === "down" && <p className="hint">Backend not reachable yet.</p>}
        </div>
        <button className="primary" onClick={run} disabled={!canRun}>
          {loading ? "Analysing…" : image && text.trim().length >= 10 ? "Analyse image and report" : image ? "Analyse image" : "Explain this report"}
        </button>
      </div>
      <footer className="foot">{(result && result.disclaimer) || "MedTruth AI explains and checks; it does not diagnose."}</footer>
    </div>
  );
}
