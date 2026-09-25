"""Lossless source sharing for prompts; raw measured evidence stays unchanged."""
import json


def _edit(base, source):
    if base == source:
        return []
    if not base:
        return None
    prefix = 0
    limit = min(len(base), len(source))
    while prefix < limit and base[prefix] == source[prefix]:
        prefix += 1
    suffix = 0
    while suffix < limit-prefix and base[-1-suffix] == source[-1-suffix]:
        suffix += 1
    context = 32
    while True:
        start = max(0, prefix-context)
        old_end = min(len(base), len(base)-suffix+context)
        new_end = min(len(source), len(source)-suffix+context)
        old, new = base[start:old_end], source[start:new_end]
        if old and base.count(old) == 1:
            return [dict(old=old, new=new)]
        context *= 2


def compact_sources(evidence):
    """Keep the first source in full; encode later sources only when shorter.

    Each patch is an exact unique replacement against the first source. It is
    presentation data, not a change to the edit bases used by candidate_source.
    """
    if not evidence:
        return []
    base = evidence[0]
    result = [dict(base)]
    for item in evidence[1:]:
        full = dict(item)
        edits = _edit(base['source'], item['source'])
        if edits is None:
            result.append(full)
            continue
        compact = {key:value for key,value in item.items() if key != 'source'}
        compact['prompt_source_patch'] = dict(display_base_hash=base['source_hash'], edits=edits)
        result.append(compact if len(json.dumps(compact)) < len(json.dumps(full)) else full)
    return result
