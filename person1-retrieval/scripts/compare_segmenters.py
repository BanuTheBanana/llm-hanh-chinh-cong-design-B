"""Run from track root: python scripts/compare_segmenters.py --help"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from person1_retrieval.comparison import run_comparison
from person1_retrieval.segmenter import SegmentationError, load_protected_terms


def main():
    parser = argparse.ArgumentParser(description='Compare local underthesea and pyvi outputs on fragments')
    parser.add_argument('--input', type=Path, default=ROOT / 'data/local/procedure_fragments.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--protected-terms', type=Path)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    output = args.output or ROOT / 'reports' / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    try:
        terms = load_protected_terms(args.protected_terms) if args.protected_terms else ()
        summary = run_comparison(args.input, output, protected_terms=terms, repeats=args.repeats, limit=args.limit)
    except (ValueError, OSError, SegmentationError) as error:
        # Do not print source content in an exception (e.g. Unicode/JSON errors).
        print(f'Comparison failed: {type(error).__name__}. Check input, dependencies and output directory.', file=sys.stderr)
        return 1
    print(f"Done: {summary['processed_fragments']} fragments; {summary['outputs_differ_count']} outputs differ.")
    print(f'Review files: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
