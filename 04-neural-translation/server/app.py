"""Aether Translation Research - language aware, evidence-first neural translation.

No offline placeholder translations. No automatic model downloads. The optional
NLLB model is research-only (CC BY-NC 4.0; verify exact checkpoint license).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal
import json
import os
import sqlite3
import threading
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.getenv("TRANSLATION_DB", str(ROOT / "data" / "translation_local.sqlite3")))
DB.parent.mkdir(parents=True, exist_ok=True)
LANGS = {
    "en": {"name": "English", "native": "English", "script": "Latin", "nllb": "eng_Latn"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "script": "Devanagari", "nllb": "hin_Deva"},
    "te": {"name": "Telugu", "native": "తెలుగు", "script": "Telugu", "nllb": "tel_Telu"},
    "ko": {"name": "Korean", "native": "한국어", "script": "Hangul", "nllb": "kor_Hang"},
}
Lang = Literal["en", "hi", "te", "ko"]


def db_connection():
    conn = sqlite3.connect(str(DB), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS translation_events (
        id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, source_lang TEXT NOT NULL,
        target_lang TEXT NOT NULL, characters INTEGER NOT NULL, model TEXT NOT NULL,
        milliseconds INTEGER NOT NULL, text_stored INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn


app = FastAPI(title="LingoAtlas — Aether Neural Translation Research", version="1.0.0")
app.mount("/assets", StaticFiles(directory=ROOT / "web" / "assets"), name="assets")


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source: Lang
    target: Lang
    max_new_tokens: int = Field(default=300, ge=16, le=512)

    @model_validator(mode="after")
    def check(self):
        if not self.text.strip():
            raise ValueError("Input must not be blank")
        return self


class EvaluationRequest(TranslationRequest):
    reference_translation: str = Field(min_length=1, max_length=5000)


_MODEL_LOCK = threading.Lock()


def model_config():
    path_raw = os.getenv("NMT_MODEL_DIR", "").strip()
    research = os.getenv("NMT_RESEARCH_MODE", "0") == "1"
    path = Path(path_raw).expanduser().resolve() if path_raw else None
    ready = bool(research and path and path.is_dir() and (path / "config.json").is_file())
    return {"ready": ready, "mode": "NLLB_RESEARCH_ONLY" if ready else "MODEL_NOT_CONFIGURED",
            "has_local_checkpoint": bool(path and path.is_dir()),
            "research_enabled": research,
            "reason": "No licensed local NLLB research model configured" if not ready else "Local checkpoint configured; inference not yet health-probed"}


@lru_cache(maxsize=1)
def load_model():
    status = model_config()
    if not status["ready"]:
        raise RuntimeError("No local research model configured. Set NMT_RESEARCH_MODE=1 and NMT_MODEL_DIR to a real local checkpoint.")
    path = Path(os.environ["NMT_MODEL_DIR"]).expanduser().resolve()
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, use_fast=False)
        model = AutoModelForSeq2SeqLM.from_pretrained(str(path), local_files_only=True)
        model.eval()
        return tokenizer, model
    except Exception as exc:
        raise RuntimeError("The local neural checkpoint could not be loaded. Check license, configuration and model files.") from exc


def neural_translate(text: str, source: Lang, target: Lang, max_new_tokens: int):
    if source == target:
        raise ValueError("Translation requires two different languages")
    import torch
    tokenizer, model = load_model()
    with _MODEL_LOCK:
        tokenizer.src_lang = LANGS[source]["nllb"]
        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
        lang_id = tokenizer.convert_tokens_to_ids(LANGS[target]["nllb"])
        if lang_id is None or lang_id == tokenizer.unk_token_id:
            raise RuntimeError("Requested target language is not supported by this checkpoint")
        with torch.inference_mode():
            result = model.generate(**encoded, forced_bos_token_id=lang_id, max_new_tokens=max_new_tokens, num_beams=4)
        translation = tokenizer.batch_decode(result, skip_special_tokens=True)[0]
    if not translation.strip():
        raise RuntimeError("Model returned empty output")
    return translation


def record_event(source: str, target: str, count: int, milliseconds: int, model_id: str):
    with db_connection() as conn:
        conn.execute("INSERT INTO translation_events VALUES(?,?,?,?,?,?,?,?)", (
            str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), source, target, count, model_id, milliseconds, 0))
        conn.commit()


@app.get("/api/health")
def health():
    status = model_config()
    return {"service": "ok", "model": status,
            "text_retention": "metadata_only_no_source_or_translation_text",
            "commercial_use": "NOT_GRANTED_FOR_NLLB_RESEARCH_CHECKPOINT",
            "claims": "No generated translations unless a local model runs"}


@app.get("/api/languages")
def languages():
    return {"languages": [{"code": code, **lang} for code, lang in LANGS.items()],
            "supported_pairs": 12, "same_language_identity_is_not_neural_translation": True,
            "model_family": "NLLB-200; research use only when configured"}


@app.post("/api/translate")
def translate(request: TranslationRequest):
    if request.source == request.target:
        raise HTTPException(422, "Choose different source and destination languages")
    if not model_config()["ready"]:
        raise HTTPException(503, "No neural model installed. This site does not fabricate translations. Add a licensed local checkpoint and enable research mode.")
    import time
    started = time.perf_counter()
    try:
        output = neural_translate(request.text, request.source, request.target, request.max_new_tokens)
    except (ValueError, RuntimeError, ImportError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
    elapsed = int((time.perf_counter() - started) * 1000)
    record_event(request.source, request.target, len(request.text), elapsed, "NLLB_local_research")
    return {"translation": output, "source": request.source, "target": request.target,
            "engine": "NLLB_LOCAL_RESEARCH", "elapsed_ms": elapsed,
            "model_is_live": True, "commercial_licensing": "not_granted",
            "input_stored": False, "quality_is_not_guaranteed": True}


@app.post("/api/evaluate")
def evaluate(request: EvaluationRequest):
    if request.source == request.target:
        raise HTTPException(422, "Select distinct language codes")
    if not model_config()["ready"]:
        raise HTTPException(503, "No local neural model to evaluate. Metrics cannot be simulated.")
    try:
        import sacrebleu
    except ImportError as exc:
        raise HTTPException(503, "Install the optional sacrebleu evaluation package") from exc
    import time
    start = time.perf_counter()
    try:
        hypothesis = neural_translate(request.text, request.source, request.target, request.max_new_tokens)
    except (ValueError, RuntimeError, ImportError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
    bleu = sacrebleu.corpus_bleu([hypothesis], [[request.reference_translation]])
    chrf = sacrebleu.corpus_chrf([hypothesis], [[request.reference_translation]], word_order=2)
    elapsed = int((time.perf_counter() - start) * 1000)
    record_event(request.source, request.target, len(request.text), elapsed, "NLLB_local_research_evaluation")
    return {"hypothesis": hypothesis, "reference": request.reference_translation,
            "metrics": {"bleu": round(bleu.score, 2), "chrf_plus_plus": round(chrf.score, 2)},
            "warning": "A single-sentence evaluation is noisy; use a held-out multi-sentence test corpus for benchmark claims.",
            "model_is_live": True, "text_stored": False}


@app.get("/api/metrics")
def metrics():
    with db_connection() as conn:
        rows = conn.execute("SELECT source_lang, target_lang, COUNT(*) AS runs, SUM(characters) AS characters FROM translation_events GROUP BY source_lang,target_lang ORDER BY runs DESC").fetchall()
        count = conn.execute("SELECT COUNT(*) FROM translation_events").fetchone()[0]
    return {"total_completed_translations_and_evaluations": count, "language_pairs": [dict(r) for r in rows],
            "content_retained": False, "local_device_database": True}


@app.get("/")
def home():
    return FileResponse(ROOT / "web" / "index.html")
