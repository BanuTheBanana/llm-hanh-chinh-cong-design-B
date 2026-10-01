import unicodedata
from uuid import uuid4

from app.legacy.conversation_state import is_follow_up, resolve_filters
from app.legacy.interpretation import extract_explicit_filters, requested_section_types


def build_interpretation_trace(query, segmenter, supplied_filters, state, session_id, top_k):
    normalized = unicodedata.normalize('NFC', ' '.join(query.split()))
    explicit_filters = extract_explicit_filters(normalized)
    resolved_filters = resolve_filters(normalized, supplied_filters, state)
    segmented = segmenter.segment(normalized)
    retrieval_input = {
        'query_text_raw': query,
        'query_text_segmented': segmented,
        'filters': resolved_filters,
        'conversation_session_id': session_id,
        'top_k': top_k,
    }
    previous = state or {}
    return {
        'trace_id': str(uuid4()),
        'query_text_raw': query,
        'normalized_query_text': normalized,
        'segmented_query_text': segmented,
        'explicit_filters': explicit_filters,
        'resolved_filters': resolved_filters,
        'requested_section_types': requested_section_types(normalized),
        'follow_up': is_follow_up(normalized),
        'prior_state': {
            'exists': bool(state),
            'active_filters': previous.get('active_filters', {}),
            'last_resolved_procedure_id': previous.get('last_resolved_procedure_id'),
            'last_requested_section_types': previous.get('last_requested_section_types', []),
            'unresolved_references': previous.get('unresolved_references', []),
        },
        'segmenter': segmenter.metadata(),
        'interpretation_outcome': 'ready_for_retrieval',
        'retrieval_input': retrieval_input,
    }