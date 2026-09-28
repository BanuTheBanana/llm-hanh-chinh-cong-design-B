import unicodedata
import pytest
from person1_retrieval import segmenter as mod
from person1_retrieval.segmenter import SegmenterConfig, SegmentationError, VietnameseSegmenter, normalize_text, load_protected_terms


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setattr(mod, '_load_backend', lambda name: lambda text: text)


def test_nfc_whitespace_preserves_legal_characters():
    original = '  Lệ\t phí:\n50.000đ; số 60/2014/QH13. '
    assert normalize_text(unicodedata.normalize('NFD', original)) == 'Lệ phí: 50.000đ; số 60/2014/QH13.'


@pytest.mark.parametrize('value', [None, 12, [], {}])
def test_invalid_input_type(value):
    with pytest.raises(TypeError):
        VietnameseSegmenter().segment(value)


def test_empty_never_loads_backend(monkeypatch):
    def fail(name):
        raise AssertionError('must not load backend')
    monkeypatch.setattr(mod, '_load_backend', fail)
    assert VietnameseSegmenter().segment(' \t\n') == ''


def test_longest_phrase_boundary_case_and_repetition(identity):
    engine = VietnameseSegmenter(SegmenterConfig('pyvi', ('hộ kinh', 'hộ kinh doanh')))
    assert engine.segment('Hộ kinh doanh; hộ kinh doanh. Hộ kinh doanhnghiệp') == 'Hộ_kinh_doanh ; hộ_kinh_doanh . Hộ_kinh doanhnghiệp'
    assert VietnameseSegmenter(SegmenterConfig('pyvi', ('hộ kinh doanh',))).segment('hộ kinh doanhnghiệp') == 'hộ kinh doanhnghiệp'


def test_terms_preserve_unicode_and_source_case(identity):
    engine = VietnameseSegmenter(SegmenterConfig('pyvi', ('hộ kinh doanh',)))
    assert engine.segment(unicodedata.normalize('NFD', 'HỘ KINH DOANH')) == 'HỘ_KINH_DOANH'


def test_existing_underscore_is_not_rewritten(identity):
    assert VietnameseSegmenter().segment('mã_hồ_sơ A_1') == 'mã_hồ_sơ A_1'


def test_config_deduplicates_and_is_deterministic():
    first = SegmenterConfig('pyvi', ('Hộ kinh doanh', 'hộ kinh doanh', 'hộ kinh'))
    second = SegmenterConfig('pyvi', ('hộ kinh', 'hộ kinh doanh'))
    assert first == second
    assert VietnameseSegmenter(first).metadata() == VietnameseSegmenter(second).metadata()
    assert VietnameseSegmenter(first).metadata()['config_fingerprint'] != VietnameseSegmenter().metadata()['config_fingerprint']


@pytest.mark.parametrize('kwargs', [{'backend': 'unknown'}, {'protected_terms': ('',)}, {'protected_terms': ('a.*',)}, {'protected_terms': ('hộ_kinh',)}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        SegmenterConfig(**kwargs)


def test_term_file(tmp_path):
    p = tmp_path / 'terms.txt'
    p.write_text('\ufeff# comment\n\nhộ kinh doanh\n', encoding='utf-8')
    assert load_protected_terms(p) == ('hộ kinh doanh',)


def test_dependency_error_does_not_silently_fallback(monkeypatch):
    def fail(name):
        raise SegmentationError('missing model')
    monkeypatch.setattr(mod, '_load_backend', fail)
    with pytest.raises(SegmentationError):
        VietnameseSegmenter().segment('hồ sơ')


def test_backend_exception_does_not_expose_input(monkeypatch):
    def crash(text):
        raise RuntimeError(text)
    monkeypatch.setattr(mod, '_load_backend', lambda name: crash)
    with pytest.raises(SegmentationError) as exc:
        VietnameseSegmenter().segment('PRIVATE_INPUT_123')
    assert 'PRIVATE_INPUT_123' not in str(exc.value)


def test_public_function_matches_instance(identity):
    assert mod.segment('  Hồ sơ\n mới ') == VietnameseSegmenter().segment('  Hồ sơ\n mới ')
