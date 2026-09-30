"""Shared Vietnamese segmentation for corpus and query; no network API calls."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib import metadata
from pathlib import Path
import json
import re
import unicodedata
from typing import Callable

WRAPPER_VERSION = '1.0.0'
BACKENDS = ('underthesea', 'pyvi')


class SegmentationError(RuntimeError):
    """Dependency/model/backend failure. No silent whitespace fallback."""


def normalize_text(text: str) -> str:
    """NFC + whitespace only. Preserve case, accents, punctuation and digits."""
    if not isinstance(text, str):
        raise TypeError('text must be a str')
    return ' '.join(unicodedata.normalize('NFC', text).split())


def load_protected_terms(path: str | Path) -> tuple[str, ...]:
    """UTF-8 text, one phrase per line; empty lines and # comments ignored."""
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#'))


@dataclass(frozen=True)
class SegmenterConfig:
    backend: str = 'underthesea'  # integration default, NOT a benchmark winner
    protected_terms: tuple[str, ...] = ()

    def __post_init__(self):
        if self.backend not in BACKENDS:
            raise ValueError(f'backend must be one of {BACKENDS}')
        if isinstance(self.protected_terms, str):
            raise TypeError('protected_terms must be a sequence of phrases, not one str')
        terms = set()
        for term in self.protected_terms:
            term = normalize_text(term)
            if not term:
                raise ValueError('protected terms cannot be empty')
            # Terms are lexical phrases, not arbitrary regexes or URLs.
            if not re.fullmatch(r'[^\W_]+(?: [^\W_]+)*', term, re.UNICODE):
                raise ValueError('protected terms must contain words separated by spaces')
            terms.add(term.casefold())
        object.__setattr__(self, 'protected_terms', tuple(sorted(terms, key=lambda t: (-len(t), t))))


@lru_cache(maxsize=2)
def _load_backend(name: str) -> Callable[[str], str]:
    """Lazy import and model reuse; no corpus content included in errors."""
    try:
        if name == 'underthesea':
            from underthesea import word_tokenize
            # Disable spelling/token normalization: this is segmentation only.
            return lambda text: word_tokenize(text, format='text', use_token_normalize=False)
        if name == 'pyvi':
            from pyvi import ViTokenizer
            return ViTokenizer.tokenize
    except Exception:
        raise SegmentationError(f'Cannot load {name}; install requirements.txt and check its local model files') from None
    raise ValueError(f'Unsupported backend: {name}')


class VietnameseSegmenter:
    """One instance/config must be reused for index-time and query-time text."""

    def __init__(self, config: SegmenterConfig | None = None):
        self.config = config or SegmenterConfig()
        terms = self.config.protected_terms
        self._pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(t) for t in terms) + r')(?!\w)', re.I) if terms else None

    def _segment_chunk(self, text: str) -> str:
        if not text.strip():
            return ''
        try:
            result = _load_backend(self.config.backend)(text.strip())
        except SegmentationError:
            raise
        except Exception:
            raise SegmentationError(f'{self.config.backend} failed while segmenting an input') from None
        if not isinstance(result, str) or not result.strip():
            raise SegmentationError(f'{self.config.backend} returned an invalid result')
        return normalize_text(result)

    def segment(self, text: str) -> str:
        text = normalize_text(text)
        if not text:
            return ''
        if self._pattern is None:
            return self._segment_chunk(text)
        # Match original spans first, longest phrase first; bypass tokenizer for
        # protected phrases. No placeholder that a tokenizer could corrupt.
        parts, cursor = [], 0
        for match in self._pattern.finditer(text):
            parts.append(self._segment_chunk(text[cursor:match.start()]))
            parts.append(match.group().replace(' ', '_'))
            cursor = match.end()
        parts.append(self._segment_chunk(text[cursor:]))
        return ' '.join(part for part in parts if part)

    def metadata(self) -> dict:
        try:
            version = metadata.version(self.config.backend)
        except metadata.PackageNotFoundError:
            version = 'not-installed'
        config = {'wrapper_version': WRAPPER_VERSION, 'backend': self.config.backend,
                  'backend_version': version, 'normalization': 'NFC+whitespace; preserve-case',
                  'protected_terms': list(self.config.protected_terms),
                  'underthesea_use_token_normalize': False}
        encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return {**config, 'config_fingerprint': sha256(encoded.encode('utf-8')).hexdigest()}


@lru_cache(maxsize=1)
def _default_segmenter() -> VietnameseSegmenter:
    return VietnameseSegmenter()


def segment(text: str) -> str:
    """Public entry point for Person 2. Default underthesea, no protected terms."""
    return _default_segmenter().segment(text)
