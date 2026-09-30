"""Compare outputs, not accuracy: there is no gold segmentation in this corpus."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .segmenter import BACKENDS, SegmenterConfig, VietnameseSegmenter, normalize_text


def load_fragments(path: str | Path) -> list[dict]:
    objects = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(objects, list) or not objects:
        raise ValueError('Expected a non-empty JSON array of fragments')
    seen = set()
    for i, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise ValueError(f'Fragment at index {i} must be an object')
        fid = obj.get('fragment_id')
        if not isinstance(fid, str) or not fid.strip() or fid in seen:
            raise ValueError(f'Fragment at index {i} has missing/duplicate ID')
        seen.add(fid)
        if not isinstance(obj.get('text'), str) or not normalize_text(obj['text']):
            raise ValueError(f'Fragment at index {i} has invalid/empty text')
    return objects


def csv_safe(value):
    """Excel formula-injection guard for review CSV; JSONL retains exact text."""
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def run_comparison(input_path: str | Path, output_dir: str | Path, *,
                   protected_terms: tuple[str, ...] = (), repeats: int = 1,
                   limit: int | None = None) -> dict:
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats must be a positive integer')
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError('limit must be a positive integer')
    input_path, output_dir = Path(input_path), Path(output_dir)
    fragments = load_fragments(input_path)
    selected = fragments if limit is None else fragments[:limit]
    # Avoid overwriting the input or a prior review. Use a new directory per run.
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError('Output directory is not empty; choose a new run directory')
    segmenters = {name: VietnameseSegmenter(SegmenterConfig(name, protected_terms)) for name in BACKENDS}
    warmup = {}
    for name, engine in segmenters.items():
        start = perf_counter()
        engine.segment('Đây là câu khởi động bộ tách từ.')
        warmup[name] = (perf_counter() - start) * 1000
    results = []
    for i, fragment in enumerate(selected):
        row = {'fragment_id': fragment['fragment_id'], 'original_text': fragment['text'],
               'normalized_text': normalize_text(fragment['text'])}
        for name, engine in segmenters.items():
            timings, outputs = [], []
            for _ in range(repeats):
                start = perf_counter()
                outputs.append(engine.segment(fragment['text']))
                timings.append((perf_counter() - start) * 1000)
            row[name] = outputs[0]
            row[name + '_ms'] = statistics.median(timings)
            row[name + '_repeat_consistent'] = len(set(outputs)) == 1
            row[name + '_token_count'] = len(outputs[0].split())
        row['outputs_differ'] = row[BACKENDS[0]] != row[BACKENDS[1]]
        row['review_notes'] = ''
        results.append(row)
        if (i + 1) % 25 == 0:
            print(f'Processed {i+1}/{len(selected)} fragments', flush=True)
    summary = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
        'total_fragments': len(fragments), 'processed_fragments': len(selected),
        'selection': 'all' if limit is None else 'first_n_in_input_order',
        'repeats': repeats, 'python_version': platform.python_version(),
        'platform': platform.platform(),
        'outputs_differ_count': sum(row['outputs_differ'] for row in results),
        'backends': {},
        'quality_evaluation': 'not_scored_no_gold_labels',
        'note': 'Different outputs are review candidates, not proven errors. Timings exclude warmup; no winner selected.',
    }
    for name, engine in segmenters.items():
        times = [row[name + '_ms'] for row in results]
        summary['backends'][name] = {
            **engine.metadata(), 'warmup_ms': warmup[name],
            'median_fragment_ms': statistics.median(times),
            'sum_fragment_median_ms': sum(times),
            'total_tokens': sum(row[name + '_token_count'] for row in results),
            'repeat_inconsistent_count': sum(not row[name + '_repeat_consistent'] for row in results),
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'comparison.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in results), encoding='utf-8')
    with (output_dir / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows({key: csv_safe(value) for key, value in row.items()} for row in results)
    (output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary
