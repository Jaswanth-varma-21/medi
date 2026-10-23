"""Orchestrates the four agents: Analysis -> Retrieval -> Explanation -> Verification."""
from .agents.analysis_agent import analyze
from .agents.explanation_agent import explain
from .agents.retrieval_agent import Retriever, retrieve_for_finding
from .agents.verification_agent import verify
from .image_findings import kb_entry
from .knowledge_base import KnowledgeBase
from .llm import LLMClient

DISCLAIMER = (
    "MedTruth AI explains the wording of an X-ray report. It does not diagnose, "
    "and it does not replace your doctor or the radiologist."
)
MAX_CHARS = 20000


class Pipeline:
    def __init__(self, kb=None, llm=None):
        self.kb = kb or KnowledgeBase()
        self.retriever = Retriever(self.kb)
        self.llm = llm if llm is not None else LLMClient()

    def explain_image_findings(self, observations: list, use_llm: bool = True) -> list:
        """Explain and verify the FLAGGED image-model observations with the same agents used for reports.

        Results carry source='image' so they are never mixed up with findings read from a written report.
        """
        llm = self.llm if use_llm else None
        out = []
        for i, o in enumerate(x for x in observations if x.get("flagged")):
            entry_id = kb_entry(o["finding"], self.kb)
            entry = self.kb.by_id.get(entry_id) if entry_id else None
            title = entry["title"] if entry else o["finding"]
            sentence = f"The image model flagged a possible {title.lower()}. This is a computer estimate, not a confirmed finding."
            f = {"sentence_index": -1, "sentence": sentence, "entry_id": entry_id, "term": title,
                 "status": "uncertain", "source": "image"}
            evidence = retrieve_for_finding(self.retriever, f) if entry else []
            explanation = explain(f, evidence, self.kb, llm)
            verification = verify(f, explanation, evidence, entry["kind"] if entry else "abnormal", sentence)
            out.append(
                {
                    "id": i, "source": "image", "sentence_index": -1, "sentence": sentence, "term": title,
                    "title": o["finding"], "kind": entry["kind"] if entry else "abnormal",
                    "urgency": entry["urgency"] if entry else "discuss", "status": "uncertain",
                    "model_score": o["score"],
                    "evidence": [{k: e[k] for k in ("entry_id", "title", "summary", "source", "score")} for e in evidence],
                    "explanation": {"text": explanation["text"], "method": explanation["method"]},
                    "verification": verification,
                }
            )
        return out

    def run(self, report_text: str, use_llm: bool = True) -> dict:
        report_text = (report_text or "").strip()
        if len(report_text) < 10:
            raise ValueError("The report text is too short to analyse.")
        if len(report_text) > MAX_CHARS:
            raise ValueError(f"The report text is longer than {MAX_CHARS} characters.")

        llm = self.llm if use_llm else None
        trace = []

        analysis = analyze(report_text, self.kb)
        sentences, raw = analysis["sentences"], analysis["findings"]
        trace.append({"agent": "Analysis Agent", "output": f"Read {len(sentences)} sentences and found {len(raw)} findings."})

        findings, retrieved_total = [], 0
        for i, f in enumerate(raw):
            evidence = retrieve_for_finding(self.retriever, f)
            retrieved_total += len(evidence)
            explanation = explain(f, evidence, self.kb, llm)
            entry = self.kb.by_id[f["entry_id"]]
            verification = verify(f, explanation, evidence, entry["kind"], report_text)
            findings.append(
                {
                    "id": i,
                    "sentence_index": f["sentence_index"],
                    "sentence": f["sentence"],
                    "term": f["term"],
                    "title": entry["title"],
                    "kind": entry["kind"],
                    "urgency": entry["urgency"],
                    "status": f["status"],
                    "evidence": [
                        {k: e[k] for k in ("entry_id", "title", "summary", "source", "score")} for e in evidence
                    ],
                    "explanation": {"text": explanation["text"], "method": explanation["method"]},
                    "verification": verification,
                }
            )
        trace.append({"agent": "Retrieval Agent", "output": f"Retrieved {retrieved_total} evidence passages."})
        methods = sorted({f["explanation"]["method"] for f in findings})
        trace.append({"agent": "Explanation Agent", "output": "Wrote explanations using: " + (", ".join(methods) or "nothing to explain") + "."})
        flagged = sum(1 for f in findings if f["verification"]["status"] in ("flagged", "no_evidence"))
        trace.append({"agent": "Verification Agent", "output": f"Checked every claim; {flagged} finding(s) flagged."})

        scored = [f["verification"]["score"] for f in findings if f["verification"]["claims"]]
        return {
            "sentences": sentences,
            "findings": findings,
            "summary": {
                "findings": len(findings),
                "verified": sum(1 for f in findings if f["verification"]["status"] == "verified"),
                "flagged": flagged,
                "faithfulness": round(sum(scored) / len(scored), 2) if scored else None,
            },
            "trace": trace,
            "llm": {"enabled": bool(llm and llm.enabled), "model": llm.model if llm and llm.enabled else None},
            "knowledge_base": self.kb.meta["name"] + " v" + self.kb.meta["version"],
            "disclaimer": DISCLAIMER,
        }
