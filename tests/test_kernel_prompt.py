from copy import deepcopy
import hashlib
import json

import pytest

from sera.kernel_prompt import compact_sources


def restore(records):
    sources = {}
    for record in records:
        if 'source' in record:
            source = record['source']
        else:
            patch = record['prompt_source_patch']
            source = sources[patch['display_base_hash']]
            for edit in patch['edits']:
                assert edit['old'] and source.count(edit['old']) == 1
                source = source.replace(edit['old'], edit['new'], 1)
        sources[record['source_hash']] = source
    return [sources[r['source_hash']] for r in records]


@pytest.mark.parametrize('base,source', [
    ('abc', 'abc'), ('abc', 'abc suffix'), ('abc', 'prefix abc'),
    ('abc def', 'abc'), ('abcdef', 'def'), ('abc', 'xyz'),
    ('aaa'*1000, 'aaa'*500+'b'+'aaa'*500), ('α\ntext\n', 'α\ntext'),
])
def test_sources_round_trip_without_changing_metadata_or_input(base, source):
    records = [dict(source=s, source_hash=str(i), scores=[10+i], status='passed')
               for i,s in enumerate((base, source))]
    before = deepcopy(records)
    compact = compact_sources(records)
    assert records == before
    assert restore(compact) == [base, source]
    assert [{k:v for k,v in r.items() if k not in ('source','prompt_source_patch')}
            for r in compact] == [{k:v for k,v in r.items() if k != 'source'} for r in records]
    assert compact_sources(records) == compact
    assert len(json.dumps(compact)) <= len(json.dumps(records))


def test_seven_large_related_kernels_fit_without_dropping_measured_evidence():
    base = ''.join(f'float value_{i} = {i};\n' for i in range(8000))
    records = []
    for i in range(7):
        source = base.replace('value_4000 = 4000', f'value_4000 = {4000+i}')
        records.append(dict(source=source,source_hash=hashlib.sha256(source.encode()).hexdigest(),
                            scores=[1000+i]*10,control_scores=[1000]*10,status='passed'))
    assert len(json.dumps(records)) > 1048576
    compact = compact_sources(records)
    assert len(json.dumps(compact)) < 300000
    assert restore(compact) == [r['source'] for r in records]
