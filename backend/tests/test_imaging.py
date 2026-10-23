import io
import unittest

import numpy as np
from PIL import Image

from app.imaging import ImageError, validate_image
from app.vision import run_model


def png(arr, mode="L"):
    b = io.BytesIO()
    Image.fromarray(arr, mode).save(b, "PNG")
    return b.getvalue()


class ImagingTests(unittest.TestCase):
    def test_rejects_non_image(self):
        with self.assertRaises(ImageError):
            validate_image(b"not an image")

    def test_flat_small_image_warns(self):
        _, exam, q = validate_image(png(np.full((300, 300), 120, np.uint8)))
        codes = {w["code"] for w in q["warnings"]}
        self.assertIn("low_contrast", codes)
        self.assertIn("low_resolution", codes)
        self.assertIsNone(exam["view"])

    def test_no_model_means_no_findings(self):
        rng = np.random.default_rng(0)
        gray, _, q = validate_image(png(rng.integers(0, 255, (600, 600), dtype=np.uint8)))
        out = run_model("chest", gray, q)
        self.assertEqual(out["status"], "no_model")
        self.assertEqual(out["observations"], [])


if __name__ == "__main__":
    unittest.main()


class ImageExplainTests(unittest.TestCase):
    def test_flagged_image_finding_is_explained_and_verified(self):
        from app.pipeline import Pipeline
        from app.report import build_html
        p = Pipeline(llm=None)
        obs = [{"finding": "Effusion", "location": "x", "score": 0.8, "threshold": 0.5, "flagged": True},
               {"finding": "Cardiomegaly", "location": "x", "score": 0.1, "threshold": 0.5, "flagged": False},
               {"finding": "Fibrosis", "location": "x", "score": 0.9, "threshold": 0.5, "flagged": True}]
        out = p.explain_image_findings(obs, use_llm=False)
        self.assertEqual(len(out), 2)  # unflagged ones are not explained
        self.assertTrue(all(f["source"] == "image" for f in out))
        self.assertIn("computer estimate", out[0]["explanation"]["text"])
        self.assertNotEqual(out[0]["verification"]["status"], "no_evidence")
        self.assertEqual(out[1]["verification"]["status"], "no_evidence")  # no safe KB match: no guess
        html = build_html({"exam": {"label": "<b>x</b>"}, "analysis": {"status": "ok", "observations": obs, "limitations": []},
                           "explanations": out}, None)
        self.assertIn("From the image model", html)
        self.assertNotIn("<b>x</b>", html)  # escaped
