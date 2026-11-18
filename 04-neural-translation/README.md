# LingoAtlas — Project 04 / Neural Machine Translation Laboratory

A standalone responsive neural translation website for **English, Hindi, Telugu and Korean**, including their script-specific typography, side-by-side editing, text copy, twelve translation directions, research metric panels, and a genuine adapter for an independently downloaded **locally installed** NLLB-style Transformer checkpoint.

## Running the local site

```bash
python -m pip install -r requirements.txt
uvicorn server.app:app --reload --port 8004
```

Open <http://localhost:8004> and <http://localhost:8004/docs>. `pytest -q` runs the backend tests; `node --check web/assets/app.js` checks the JavaScript syntax.

## Authentic neural inference (optional; **noncommercial research only**)

No model weights are included in this package, no dummy translations are returned, and the app **will not download a checkpoint without your action**.

1. Research the specific checkpoint and verify its license and provenance. The common NLLB-200 research model is released under **CC BY-NC 4.0** and is **not** a commercial model license. Other checkpoints must have their own individual licenses checked.
2. Independently acquire the appropriate model checkpoint and place the **complete checkpoint directory** on your own machine. It must contain `config.json`, tokenizer resources, and actual weight files. The `NMT_MODEL_DIR` is a *path*, not a model name or remote URL.
3. Install optional dependencies: `pip install -r requirements-ml.txt` (including torch); validate your own supported hardware and Python environment.
4. Set `NMT_RESEARCH_MODE=1` and `NMT_MODEL_DIR=/your/path/to/nllb-checkpoint` in your process environment, then launch the server. The model is loaded lazily by the first translation call.
5. Use the UI, which calls `/api/translate` and gets real text only after a real inference operation succeeds. Outputs are not guaranteed accurate.

The optional `/api/evaluate` endpoint runs actual **SacreBLEU BLEU and chrF++** against a human reference translation; single-sentence results are not robust benchmarks. For defensible comparisons, evaluate on a held-out collection with diverse passages and domain coverage. For Indian-language pairs, **IndicTrans2** is another research avenue, but does not natively cover Korean in its standard Indic model group.

## API

| Route | Method | Action |
|---|---|---|
| `/api/health` | GET | Live local readiness and research licensing warning |
| `/api/languages` | GET | Supported languages and scripts |
| `/api/translate` | POST | Actual model translation; `503` if model absent |
| `/api/evaluate` | POST | Genuine NMT output vs supplied human reference; `503` if absent |
| `/api/metrics` | GET | Count of completed tasks and language directions |

Example payload: `{"text":"Welcome","source":"en","target":"te","max_new_tokens":300}`. Input text and translation text are never written to the local SQLite metrics DB. Only language codes, character counts, duration and a model label are recorded. User content may still be retained in application/server memory while the request is processed; avoid logging full request bodies in deployment.

## Production readiness

This package is **not production-ready**: it needs a verified licensed commercial-capable model for commercial deployment, model sizing, resource tests, secured user accounts, rate limiting, quality evaluation, operational monitoring, and defined privacy/retention policy. No paid API, cloud database, GPU job or public deployment has been activated.

## Sources

- IndicTrans2: https://github.com/AI4Bharat/IndicTrans2
- NLLB: https://huggingface.co/facebook/nllb-200-distilled-600M (see exact model license)
- FLORES-200: https://github.com/facebookresearch/flores
- SacreBLEU: https://github.com/mjpost/sacrebleu
- Transformer sequence-to-sequence overview: https://arxiv.org/abs/1706.03762
