"""Compare frozen uploaded G3 retrieval to G4 on the same single-turn DEV records."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import g4_baseline_retrieval as baseline  # noqa: E402

from app.rag.corpus import CorpusError  # noqa: E402
from app.rag.g3.validator import load_serving  # noqa: E402
from app.rag.g4.evaluation import benchmark, read_dev  # noqa: E402
from app.rag.retrieval import normalize  # noqa: E402


def old_fields(query):
    q = " " + normalize(query) + " "
    return {
        field
        for field, phrases in baseline.INTENTS.items()
        if any(" " + phrase + " " in q for phrase in phrases)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-rows", type=int, default=10)
    parser.add_argument("--dev", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = load_serving(args.dataset, args.version, args.expected_rows)
        rows, sha = read_dev(args.dev)
        print(
            json.dumps(
                {
                    "dataset_version": data.version,
                    "dev_sha256": sha,
                    "corpus_sha256": data.fingerprint,
                    "before_single_turn": benchmark(
                        data, rows, baseline.retrieve, old_fields, include_multiturn=False
                    ),
                    "after_single_turn": benchmark(
                        data, rows, include_multiturn=False
                    ),
                    "after_all_scenarios": benchmark(data, rows),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except CorpusError as exc:
        print(json.dumps({"error": str(exc)}))
    except Exception:
        print('{"error":"DEV_COMPARISON_FAILED"}')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
