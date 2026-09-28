"""Real model smoke checks; these do not measure legal segmentation accuracy."""
import re
import pytest
from person1_retrieval.segmenter import VietnameseSegmenter, SegmenterConfig, normalize_text


@pytest.mark.integration
@pytest.mark.parametrize('backend', ['underthesea', 'pyvi'])
def test_real_backend(backend):
    pytest.importorskip(backend)
    engine = VietnameseSegmenter(SegmenterConfig(backend))
    text = 'Người dân nộp hồ sơ tại cơ quan có thẩm quyền.'
    result = engine.segment(text)
    assert result and engine.segment(text) == result
    assert re.sub(r'[\s_]', '', result) == re.sub(r'\s', '', normalize_text(text))
    protected = VietnameseSegmenter(SegmenterConfig(backend, ('hộ kinh doanh',)))
    assert 'hộ_kinh_doanh' in protected.segment('Đăng ký hộ kinh doanh.')
