"""Stable aggregation of complete specialist experiment rankings."""


def rank_experiments(proposals, ballots, *, limit):
    if not proposals or len(set(proposals)) != len(proposals):
        raise ValueError('Experiment IDs must be nonempty and distinct')
    if type(limit) is not int or limit < 1:
        raise ValueError('Batch limit must be positive')
    if not ballots:
        raise ValueError('Experiment selection requires specialist rankings')
    scores = dict.fromkeys(proposals, 0)
    for ballot in ballots:
        if (not isinstance(ballot, list) or len(ballot) != len(proposals) or
                any(not isinstance(item, str) for item in ballot) or
                len(set(ballot)) != len(proposals) or set(ballot) != set(proposals)):
            raise ValueError('Each ballot must rank each proposed experiment exactly once')
        for rank, experiment in enumerate(ballot):
            scores[experiment] += len(proposals) - rank
    return sorted(proposals, key=lambda key: (-scores[key], key))[:limit]
