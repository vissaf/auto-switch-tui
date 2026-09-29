"""Semantic similarity layer (optional, local).

Embeds each job description and each portfolio chunk with a small ONNX model
(fastembed / BAAI/bge-small-en-v1.5) and returns, per job, a 0–100 similarity
score: the max cosine similarity between the job and any evidence chunk, rescaled.

This gives synonym-rich JDs (that token matching misses) a transferable-credit
boost — e.g. a JD phrasing requirements differently from the alias list.

The whole layer is a soft dependency: if fastembed isn't installed, the model
can't download, or there's no corpus, :func:`semantic_scores` returns ``None``
and ranking falls back to the structural score only.

Performance notes (onnxruntime on CPU ~0.9ms/word):
- Job text is truncated to the first ``_JD_MAX_WORDS`` words — the requirements
  live at the top of a JD; the tail is boilerplate (benefits, EEO statements).
- The corpus is static between profile edits, so its embeddings are cached to
  ``~/.cache/auto-switch/semantic/`` keyed by content hash.
- Job embeddings are cached per job (keyed by id + truncated text hash) in
  ``~/.cache/auto-switch/semantic/jd/`` — re-embedding hundreds of JDs on CPU
  was the dominant cost of a run; now only new/changed jobs are embedded.
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import numpy as np

# bge-small cosine similarities for short texts live in a compressed band
# (max-pool vs a diverse corpus: ~0.58 unrelated to ~0.85 highly related).
# Rescale that band to 0–100.
_LOW = 0.58
_HIGH = 0.85

_NOTES_RE = re.compile(r"^#{1,3}\s*(notes for accuracy|notes for recruiters|notes)\b", re.I | re.M)

# bge-small has a ~512-token window; keep inputs bounded for speed.
_MAX_WORDS = 300      # corpus chunks
_JD_MAX_WORDS = 150   # job text (title + first N words of description)


def _chunk_words(text: str, limit: int) -> str:
    words = text.split()
    return " ".join(words[:limit])


def _split_sections(text: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                chunks.append(" ".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append(" ".join(current))
    return [_chunk_words(c, _MAX_WORDS) for c in chunks if len(c.split()) >= 8]


def build_corpus(workspace: str | Path) -> list[str]:
    from .paths import experiences_dir, profile_path

    root = Path(workspace)
    chunks: list[str] = []
    profile = profile_path(root)
    if profile.exists():
        chunks.extend(_split_sections(profile.read_text(encoding="utf-8")))

    exp_dir = experiences_dir(root)
    if exp_dir.exists():
        for name in ("PORTFOLIO.md", "RESUME_BULLETS.md"):
            for f in exp_dir.glob(f"**/{name}"):
                try:
                    text = f.read_text(encoding="utf-8")
                except Exception:
                    continue
                m = _NOTES_RE.search(text)
                if m:
                    text = text[: m.start()]
                chunks.extend(_split_sections(text))
    return chunks


def _rescale(sim: float) -> float:
    return max(0.0, min(100.0, 100.0 * (sim - _LOW) / (_HIGH - _LOW)))


def _cache_dir() -> Path:
    d = Path.home() / ".cache" / "auto-switch" / "semantic"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _corpus_embeddings(get_model, corpus: list[str]) -> np.ndarray:
    """Embed the corpus, caching to disk keyed by content hash."""
    cache_dir = _cache_dir()
    key = hashlib.sha1("\n".join(corpus).encode("utf-8")).hexdigest()[:16]
    path = cache_dir / f"corpus_{key}.npy"
    if path.exists():
        try:
            return np.load(path)
        except Exception:
            pass
    model = get_model()
    if model is None:
        raise RuntimeError("Embedding model unavailable")
    emb = np.asarray(list(model.embed(corpus)), dtype="float32")
    np.save(path, emb)
    for stale in cache_dir.glob("corpus_*.npy"):
        if stale != path:
            try:
                stale.unlink()
            except Exception:
                pass
    return emb


def _jd_cache_dir() -> Path:
    d = _cache_dir() / "jd"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Job embeddings live for this many days; stale ones are pruned on write.
_JD_CACHE_DAYS = 14


def _jd_embed_path(text: str) -> Path:
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]
    return _jd_cache_dir() / f"jd_{key}.npy"


def _prune_jd_cache() -> None:
    cutoff = time.time() - _JD_CACHE_DAYS * 86400
    for f in _jd_cache_dir().glob("jd_*.npy"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass


def _embed_jds(get_model, jd_texts: list[str]) -> np.ndarray:
    """Embed job texts, reusing per-job cached vectors where possible."""
    cached: dict[int, np.ndarray] = {}
    missing_idx: list[int] = []
    for i, text in enumerate(jd_texts):
        path = _jd_embed_path(text)
        try:
            if path.exists():
                cached[i] = np.load(path)
                continue
        except Exception:
            pass
        missing_idx.append(i)

    if missing_idx:
        model = get_model()
        if model is None:
            raise RuntimeError("Embedding model unavailable")
        emb = np.asarray(list(model.embed([jd_texts[i] for i in missing_idx])), dtype="float32")
        for pos, i in enumerate(missing_idx):
            vec = emb[pos]
            path = _jd_embed_path(jd_texts[i])
            try:
                np.save(path, vec)
            except Exception:
                pass
            cached[i] = vec
        _prune_jd_cache()

    return np.stack([cached[i] for i in range(len(jd_texts))])


def semantic_scores(jobs, workspace: str | Path) -> dict[str, float] | None:
    """Return {job_id: 0–100 semantic similarity}, or None if unavailable."""
    corpus = build_corpus(workspace)
    if not corpus:
        return None
    jd_texts = [_chunk_words(f"{j.title}. {j.description or ''}", _JD_MAX_WORDS) for j in jobs]
    if not any(jd_texts):
        return None

    model_holder: list = []

    def get_model():
        if not model_holder:
            try:
                from fastembed import TextEmbedding

                model_holder.append(TextEmbedding(model_name="BAAI/bge-small-en-v1.5"))
            except Exception:
                return None
        return model_holder[0]

    try:
        corpus_emb = _corpus_embeddings(get_model, corpus)
        jd_emb = _embed_jds(get_model, jd_texts)
    except Exception:
        return None

    # Normalize once.
    corpus_n = corpus_emb / (np.linalg.norm(corpus_emb, axis=1, keepdims=True) + 1e-9)
    jd_n = jd_emb / (np.linalg.norm(jd_emb, axis=1, keepdims=True) + 1e-9)

    sims = jd_n @ corpus_n.T  # (n_jobs, n_chunks)
    best = sims.max(axis=1)

    return {j.id: round(_rescale(float(s)), 1) for j, s in zip(jobs, best)}
