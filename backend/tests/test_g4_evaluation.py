"""No private data: verify benchmark isolation and immutable comparison inputs."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def evaluator():
    path = Path(__file__).parents[2] / "scripts/evaluate-g4-dev.py"
    spec = importlib.util.spec_from_file_location("evaluate_g4_dev", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release_evaluator():
    path = Path(__file__).parents[2] / "scripts/evaluate-g4-release.py"
    spec = importlib.util.spec_from_file_location("evaluate_g4_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_fixture(module, split="DEV"):
    fixture = {
        "split": split,
        "cases": [
            {"case_index": 0, "bundle": {"query": "Fictional A"}, "plan": {}},
            {"case_index": 1, "bundle": {"query": "Fictional B"}, "plan": {}},
        ],
    }
    fixture["fixture_sha256"] = module.digest(fixture)
    return fixture


def test_reports_must_stay_in_ignored_area(evaluator):
    with pytest.raises(ValueError, match="IGNORED"):
        evaluator.private_path(evaluator.ROOT / "docs/report.json")


@pytest.mark.parametrize("split", ["TEST", "TEST_V2", "TRAIN"])
def test_never_select_models_on_test(evaluator, tmp_path, monkeypatch, split):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(make_fixture(evaluator, split)), encoding="utf-8")
    monkeypatch.setattr(evaluator, "private_path", lambda path: path)
    with pytest.raises(ValueError, match="FROZEN_DEV_REQUIRED"):
        evaluator.summarize(SimpleNamespace(fixture=path))


def test_same_length_duplicate_results_are_rejected(evaluator, tmp_path, monkeypatch):
    fixture = make_fixture(evaluator)
    fixture_path, run_path = tmp_path / "fixture.json", tmp_path / "run.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    run_path.write_text(
        json.dumps(
            {
                "fixture_sha256": fixture["fixture_sha256"],
                "results": [{"case_index": 0}, {"case_index": 0}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluator, "private_path", lambda path: path)
    with pytest.raises(ValueError, match="INCOMPLETE_RUN"):
        evaluator.summarize(
            SimpleNamespace(fixture=fixture_path, plan_fixture=None, runs=[run_path])
        )


def test_plan_ablation_cannot_change_generation_inputs(evaluator, tmp_path, monkeypatch):
    original, changed = make_fixture(evaluator), make_fixture(evaluator)
    changed["cases"][0]["bundle"]["query"] = "Different fictional input"
    changed.pop("fixture_sha256")
    changed["fixture_sha256"] = evaluator.digest(changed)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    first.write_text(json.dumps(original), encoding="utf-8")
    second.write_text(json.dumps(changed), encoding="utf-8")
    monkeypatch.setattr(evaluator, "private_path", lambda path: path)
    with pytest.raises(ValueError, match="GENERATION_INPUTS_CHANGED"):
        evaluator.summarize(SimpleNamespace(fixture=first, plan_fixture=second))


def test_release_metrics_on_fictional_test_scenario(release_evaluator, tmp_path):
    from test_g3 import VERSION, write_dataset
    from test_g4 import expanded_groups

    from app.rag.g3.validator import load_serving

    data = load_serving(write_dataset(tmp_path, expanded_groups()), VERSION, 2)
    procedure = data.procedures["fictional-alpha"]
    fragment_ids = procedure["field_evidence"]["fees"]
    expected = [data.fragments[item]["text"] for item in fragment_ids]
    row = {
        "scenario_id": "fictional-test-001",
        "dataset_version": VERSION,
        "split": "TEST_V2",
        "procedure_id": "fictional-alpha",
        "field_expected": "fees",
        "question": "Mẫu Alpha có lệ phí không?",
        "expected_status": "ANSWER",
        "gold_fragment_ids": fragment_ids,
        "must_include": expected,
        "must_exclude": ["khẳng định hư cấu không được phép"],
        "is_multiturn": False,
        "turns": [{"role": "user", "text": "Mẫu Alpha có lệ phí không?"}],
    }
    result = release_evaluator.evaluate_rows(data, [row])
    assert result["gate_passed"] is True
    assert result["plan_answer_accuracy"] == 1
    assert result["critical_claim_errors"] == 0
