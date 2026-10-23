"""FastAPI backend.  Run:  uvicorn app.main:app --reload --port 8000"""
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from starlette.concurrency import run_in_threadpool

from .extract import ExtractError, extract_text
from .imaging import ImageError, validate_image
from .models import autoload
from .report import build_html
from .vision import MODALITIES, run_model
from .pipeline import Pipeline
from .samples import SAMPLES

load_dotenv()  # reads backend/.env (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY) before the pipeline starts

app = FastAPI(title="MedTruth AI", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
pipeline = Pipeline()
autoload()


class AnalyzeRequest(BaseModel):
    report_text: str = Field(..., min_length=10, max_length=20000)
    use_llm: bool = True


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_enabled": pipeline.llm.enabled, "knowledge_base": pipeline.kb.meta["name"]}


@app.get("/api/samples")
def samples():
    return SAMPLES


@app.post("/api/analyze")
def analyze_report(req: AnalyzeRequest):
    try:
        return pipeline.run(req.report_text, req.use_llm)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))


@app.post("/api/extract")
async def extract(request: Request, filename: str = ""):
    """Read report text from an uploaded file (raw bytes in the body; filename in the query string)."""
    data = await request.body()
    try:
        # OCR is slow, so run it off the event loop
        text = await run_in_threadpool(extract_text, data, filename)
    except ExtractError as err:
        raise HTTPException(status_code=422, detail=str(err))
    return {"text": text}


@app.post("/api/image/analyze")
async def analyze_image(request: Request, modality: str = "chest", view: str = "", filename: str = ""):
    """Steps 1-2: validate an X-ray image, then run the specialty model if one is installed."""
    if modality not in MODALITIES:
        raise HTTPException(status_code=422, detail="Unsupported image type. Choose chest, bone, spine or dental.")
    data = await request.body()
    try:
        gray, exam, quality = await run_in_threadpool(validate_image, data, view)
    except ImageError as err:
        raise HTTPException(status_code=422, detail=str(err))
    info = MODALITIES[modality]
    exam.update({"modality": modality, "label": info["label"], "region": info["region"], "filename": filename or None})
    result = await run_in_threadpool(run_model, modality, gray, quality)
    explanations = []
    if modality == "chest" and result["status"] == "ok":  # the knowledge base covers chest findings only
        explanations = await run_in_threadpool(pipeline.explain_image_findings, result["observations"], True)
    return {
        "exam": exam,
        "quality": quality,
        "analysis": result,
        "explanations": explanations,
        "review": {"report_status": "AI-generated draft", "clinician_review": "Pending", "final_report": "Not issued"},
        "disclaimer": "AI-generated draft for clinician review. Not a diagnosis.",
    }


@app.post("/api/report/draft", response_class=HTMLResponse)
def report_draft(payload: dict = Body(...)):
    """Assemble the A-E report draft (printable, self-contained HTML) from the results already shown on screen."""
    return build_html(payload.get("image"), payload.get("report"), payload.get("report_source") or "")
