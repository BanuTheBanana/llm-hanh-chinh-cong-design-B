"""Run the locked lightweight QLoRA candidates sequentially without opening TEST."""

from __future__ import annotations

import argparse
import atexit
import ctypes
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable).resolve()
BUNDLE = ROOT / "training/output/full-corpus-sft-v1-bundle"
RUN_ROOT = ROOT / "training/output/overnight-lightweight"
EVAL_ROOT = ROOT / "evaluation/reports/g5"


@dataclass(frozen=True)
class Candidate:
    slug: str
    model: str
    revision: str


CANDIDATES = (
    Candidate(
        "qwen3-1.7b",
        "Qwen/Qwen3-1.7B",
        "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
    ),
    Candidate(
        "qwen3.5-2b",
        "Qwen/Qwen3.5-2B",
        "15852e8c16360a2fea060d615a32b45270f8a8fc",
    ),
    Candidate(
        "qwen3-4b",
        "Qwen/Qwen3-4B-Instruct-2507",
        "cdbee75f17c01a7cc42f958dc650907174af0554",
    ),
)


def prevent_windows_sleep() -> None:
    if sys.platform != "win32":
        return
    continuous = 0x80000000
    system_required = 0x00000001
    result = ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
        continuous | system_required
    )
    if not result:
        raise OSError("WINDOWS_PREVENT_SLEEP_FAILED")

    def restore() -> None:
        ctypes.windll.kernel32.SetThreadExecutionState(continuous)  # type: ignore[attr-defined]

    atexit.register(restore)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_summary(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_logged(command: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        log.write(f"command={subprocess.list2cmdline(command)}\n")
        log.flush()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode:
        raise RuntimeError(f"COMMAND_FAILED_{completed.returncode}:{log_path}")


def validate_adapter(path: Path, candidate: Candidate, bundle_hash: str, *, smoke: bool) -> dict:
    manifest_path = path / "training_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("ADAPTER_MANIFEST_MISSING")
    manifest = load_json(manifest_path)
    if (
        manifest.get("base_model") != candidate.model
        or manifest.get("base_revision") != candidate.revision
        or manifest.get("source_manifest_sha256") != bundle_hash
        or manifest.get("test_data_used") is not False
        or manifest.get("smoke") is not smoke
    ):
        raise ValueError("ADAPTER_MANIFEST_BINDING_INVALID")
    for name, expected_hash in manifest.get("artifacts", {}).items():
        artifact = path / name
        if not artifact.is_file() or sha256(artifact) != expected_hash:
            raise ValueError("ADAPTER_ARTIFACT_HASH_INVALID")
    return manifest


def validate_evaluation(
    path: Path, candidate: Candidate, *, adapter_used: bool, validation_hash: str
) -> dict:
    report = load_json(path)
    if (
        report.get("model") != candidate.model
        or report.get("model_revision") != candidate.revision
        or report.get("adapter_used") is not adapter_used
        or report.get("test_data_used") is not False
        or report.get("validation_sha256") != validation_hash
        or report.get("count") != 40
    ):
        raise ValueError("EVALUATION_BINDING_INVALID")
    return report


def train_candidate(
    candidate: Candidate,
    *,
    smoke: bool,
    bundle_hash: str,
    logs: Path,
    preflights: Path,
) -> tuple[Path, dict, str]:
    suffix = "smoke-r16-seed42" if smoke else "full-corpus-r16-seed42"
    output = ROOT / "training/output" / f"{candidate.slug}-{suffix}"
    preflight = preflights / f"{candidate.slug}.json"
    run_logged(
        [
            str(PYTHON),
            str(ROOT / "training/preflight_qlora.py"),
            "--bundle",
            str(BUNDLE),
            "--model",
            candidate.model,
            "--revision",
            candidate.revision,
            "--max-length",
            "2304",
            "--output",
            str(preflight),
        ],
        logs / f"{candidate.slug}-preflight.log",
    )
    if load_json(preflight).get("status") != "PASS":
        raise RuntimeError("PREFLIGHT_NOT_PASS")
    if output.exists():
        if (output / "training_manifest.json").is_file():
            manifest = validate_adapter(output, candidate, bundle_hash, smoke=smoke)
            return output, manifest, "SKIPPED_COMPLETE"
        if any(output.iterdir()):
            archived = output.with_name(
                f"{output.name}.incomplete-"
                f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
            )
            output.rename(archived)
    command = [
        str(PYTHON),
        str(ROOT / "training/train_qlora.py"),
        "--bundle",
        str(BUNDLE),
        "--output",
        str(output),
        "--model",
        candidate.model,
        "--revision",
        candidate.revision,
        "--max-length",
        "2304",
        "--epochs",
        "1",
        "--learning-rate",
        "0.0002",
        "--lora-rank",
        "16",
        "--seed",
        "42",
    ]
    if smoke:
        command.append("--smoke")
    run_logged(command, logs / f"{candidate.slug}-train.log")
    return output, validate_adapter(output, candidate, bundle_hash, smoke=smoke), "TRAINED"


def evaluate_candidate(
    candidate: Candidate,
    adapter: Path,
    *,
    adapter_used: bool,
    validation_hash: str,
    logs: Path,
) -> tuple[dict, str]:
    kind = "adapter" if adapter_used else "base"
    output = EVAL_ROOT / f"overnight-{candidate.slug}-{kind}-validation.json"
    if output.exists():
        return (
            validate_evaluation(
                output,
                candidate,
                adapter_used=adapter_used,
                validation_hash=validation_hash,
            ),
            "SKIPPED_COMPLETE",
        )
    command = [
        str(PYTHON),
        str(ROOT / "training/evaluate_adapter.py"),
        "--bundle",
        str(BUNDLE),
        "--output",
        str(output),
        "--model",
        candidate.model,
        "--revision",
        candidate.revision,
        "--one-variant-per-base",
    ]
    if adapter_used:
        command.extend(["--adapter", str(adapter)])
    run_logged(command, logs / f"{candidate.slug}-{kind}-evaluation.log")
    return (
        validate_evaluation(
            output,
            candidate,
            adapter_used=adapter_used,
            validation_hash=validation_hash,
        ),
        "EVALUATED",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--cooldown-seconds", type=int, default=15)
    args = parser.parse_args()
    prevent_windows_sleep()
    if not BUNDLE.is_dir():
        raise SystemExit("OVERNIGHT_BUNDLE_MISSING")
    if shutil.disk_usage(ROOT.drive + "\\").free < 20 * 1024**3:
        raise SystemExit("OVERNIGHT_REQUIRES_20_GIB_FREE")

    bundle_manifest = load_json(BUNDLE / "manifest.json")
    if bundle_manifest.get("test_data_used") is not False:
        raise SystemExit("OVERNIGHT_TEST_DATA_PROHIBITED")
    bundle_hash = sha256(BUNDLE / "manifest.json")
    validation_hash = sha256(BUNDLE / "validation.jsonl")
    mode = "smoke" if args.smoke else "full"
    run_root = RUN_ROOT / mode
    logs = run_root / "logs"
    preflights = run_root / "preflight"
    preflights.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "summary.json"
    summary = {
        "schema_version": "overnight-lightweight-v1",
        "started_at": datetime.now().astimezone().isoformat(),
        "mode": mode,
        "bundle_manifest_sha256": bundle_hash,
        "validation_sha256": validation_hash,
        "test_data_used": False,
        "python": str(PYTHON),
        "free_disk_bytes_at_start": shutil.disk_usage(ROOT.drive + "\\").free,
        "sleep_prevention": "WINDOWS_SYSTEM_REQUIRED_WHILE_PROCESS_IS_RUNNING",
        "candidates": {},
        "status": "RUNNING",
    }
    write_summary(summary_path, summary)
    failed = False
    for candidate in CANDIDATES:
        print(f"[{candidate.slug}] start", flush=True)
        result = {"model": candidate.model, "revision": candidate.revision}
        try:
            adapter, manifest, train_action = train_candidate(
                candidate,
                smoke=args.smoke,
                bundle_hash=bundle_hash,
                logs=logs,
                preflights=preflights,
            )
            result.update(
                {
                    "adapter": str(adapter.relative_to(ROOT)),
                    "adapter_artifact_bytes": sum(
                        (adapter / name).stat().st_size
                        for name in manifest.get("artifacts", {})
                    ),
                    "train_action": train_action,
                    "train_metrics": manifest.get("train_metrics"),
                    "eval_metrics": manifest.get("eval_metrics"),
                    "resource_metrics": manifest.get("resource_metrics"),
                }
            )
            if not args.smoke:
                base_report, base_action = evaluate_candidate(
                    candidate,
                    adapter,
                    adapter_used=False,
                    validation_hash=validation_hash,
                    logs=logs,
                )
                adapter_report, adapter_action = evaluate_candidate(
                    candidate,
                    adapter,
                    adapter_used=True,
                    validation_hash=validation_hash,
                    logs=logs,
                )
                result.update(
                    {
                        "base_evaluation": base_report,
                        "base_evaluation_action": base_action,
                        "adapter_evaluation": adapter_report,
                        "adapter_evaluation_action": adapter_action,
                    }
                )
            result["status"] = "PASS"
            print(f"[{candidate.slug}] PASS", flush=True)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            failed = True
            result.update({"status": "FAIL", "error": str(error) or type(error).__name__})
            print(f"[{candidate.slug}] FAIL: {result['error']}", flush=True)
        summary["candidates"][candidate.slug] = result
        write_summary(summary_path, summary)
        if args.cooldown_seconds:
            time.sleep(args.cooldown_seconds)
    summary["finished_at"] = datetime.now().astimezone().isoformat()
    summary["status"] = "FAIL" if failed else "PASS"
    write_summary(summary_path, summary)
    print(f"summary={summary_path}")
    print(f"status={summary['status']}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
