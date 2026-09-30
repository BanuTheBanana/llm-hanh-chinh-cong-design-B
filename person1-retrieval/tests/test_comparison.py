import csv
import hashlib
import json
import pytest
from person1_retrieval import segmenter as mod
from person1_retrieval.comparison import load_fragments, run_comparison, csv_safe


def make_input(tmp_path, content=None):
    path = tmp_path / 'fragments.json'
    path.write_text(json.dumps(content if content is not None else [
        {'fragment_id': 'F1', 'text': 'Hồ sơ thử nghiệm'},
        {'fragment_id': 'F2', 'text': '=nội dung thử nghiệm'},
    ], ensure_ascii=False), encoding='utf-8')
    return path


def test_comparison_output_no_source_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, '_load_backend', lambda name: (lambda text: text if name == 'pyvi' else text.replace(' ', '_')))
    path = make_input(tmp_path)
    original = path.read_bytes()
    summary = run_comparison(path, tmp_path / 'report', repeats=2)
    assert summary['processed_fragments'] == 2
    assert summary['outputs_differ_count'] == 2
    assert summary['quality_evaluation'] == 'not_scored_no_gold_labels'
    assert summary['input_sha256'] == hashlib.sha256(original).hexdigest()
    assert path.read_bytes() == original
    rows = [json.loads(line) for line in (tmp_path / 'report/comparison.jsonl').read_text().splitlines()]
    assert rows[1]['original_text'].startswith('=')
    with (tmp_path / 'report/comparison.csv').open(encoding='utf-8-sig', newline='') as file:
        assert list(csv.DictReader(file))[1]['original_text'].startswith("'=")
    with pytest.raises(FileExistsError):
        run_comparison(path, tmp_path / 'report')


@pytest.mark.parametrize('content', [{}, [], [{'fragment_id': 'F', 'text': ''}], [{'fragment_id': 'F', 'text': 1}], [{'fragment_id': 'F', 'text': 'x'}, {'fragment_id': 'F', 'text': 'y'}]])
def test_reject_invalid_corpus(tmp_path, content):
    with pytest.raises(ValueError):
        load_fragments(make_input(tmp_path, content))


@pytest.mark.parametrize('kwargs', [{'repeats': 0}, {'repeats': True}, {'limit': 0}])
def test_invalid_options(tmp_path, kwargs):
    with pytest.raises(ValueError):
        run_comparison(make_input(tmp_path), tmp_path / 'out', **kwargs)


def test_formula_guard():
    for text in ['=1+1', '+cmd', '-item', '@x', '  =x']:
        assert csv_safe(text).startswith("'")
    assert csv_safe('Hồ sơ') == 'Hồ sơ'
