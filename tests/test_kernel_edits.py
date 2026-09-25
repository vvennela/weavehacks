import hashlib

import pytest

from sera.kernel_edits import candidate_source


def record(source):
    return {'source': source, 'source_hash': hashlib.sha256(source.encode()).hexdigest()}


def response(base, edits):
    return dict(source='', base_source_hash=base['source_hash'], edits=edits)


def test_guarded_edits_preserve_unchanged_source_and_apply_in_order():
    base = record('license\nloop one\nloop two\n')
    edited = candidate_source(response(base, [
        dict(old='loop one', new='loop three'),
        dict(old='loop two', new='loop four'),
    ]), [base])
    assert edited == 'license\nloop three\nloop four\n'
    assert base['source'] == 'license\nloop one\nloop two\n'


@pytest.mark.parametrize('old', ['', 'missing', 'loop'])
def test_empty_missing_or_ambiguous_edit_is_rejected(old):
    base = record('loop one\nloop two\n')
    with pytest.raises(ValueError):
        candidate_source(response(base, [dict(old=old, new='replacement')]), [base])


def test_unknown_or_tampered_base_is_rejected():
    base = record('original')
    edit = response(base, [dict(old='original', new='replacement')])
    with pytest.raises(ValueError, match='base'):
        candidate_source(edit, [])
    with pytest.raises(ValueError, match='hash'):
        candidate_source(edit, [{**base, 'source': 'tampered'}])


def test_complete_source_and_edits_are_mutually_exclusive():
    base = record('original')
    edit = response(base, [dict(old='original', new='replacement')])
    with pytest.raises(ValueError):
        candidate_source({**edit, 'source': 'another source'}, [base])
    assert candidate_source(dict(source='complete source'), [base]) == 'complete source'


def test_empty_implementation_is_rejected():
    base = record('original')
    with pytest.raises(ValueError):
        candidate_source(response(base, []), [base])
