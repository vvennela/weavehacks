"""Apply exact source edits to a hash-bound candidate in measured history."""

import hashlib


def candidate_source(response, evidence):
    source = response.get('source')
    edits = response.get('edits', [])
    base_hash = response.get('base_source_hash', '')
    if not isinstance(source, str) or not isinstance(edits, list):
        raise ValueError('Malformed kernel implementation')
    if source:
        if edits or base_hash:
            raise ValueError('Choose complete source or guarded edits, not both')
        return source
    if not isinstance(base_hash, str) or not base_hash or not 1 <= len(edits) <= 64:
        raise ValueError('Guarded edits require a base hash and 1 to 64 edits')
    base = next((item for item in evidence if item['source_hash'] == base_hash), None)
    if base is None:
        raise ValueError('Unknown kernel edit base')
    source = base['source']
    if hashlib.sha256(source.encode()).hexdigest() != base_hash:
        raise ValueError('Kernel edit base hash does not match source')
    for edit in edits:
        if (not isinstance(edit, dict) or set(edit) != {'old', 'new'} or
                not isinstance(edit['old'], str) or not isinstance(edit['new'], str) or
                not edit['old'] or source.count(edit['old']) != 1):
            raise ValueError('Each edit must match exactly one nonempty source span')
        source = source.replace(edit['old'], edit['new'], 1)
    if not source:
        raise ValueError('Kernel edits produced an empty source')
    return source
