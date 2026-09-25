import pytest

from sera.kernel_swarm_plan import rank_experiments


def test_shared_rankings_choose_batch_independent_of_ballot_order():
    proposals=['packing','schedule','tiles']
    ballots=[['schedule','packing','tiles'],['packing','schedule','tiles'],['schedule','tiles','packing']]
    assert rank_experiments(proposals,ballots,limit=2)==['schedule','packing']
    assert rank_experiments(proposals,list(reversed(ballots)),limit=2)==['schedule','packing']


def test_tied_rankings_use_stable_proposal_id():
    assert rank_experiments(['b','a'],[['a','b'],['b','a']],limit=2)==['a','b']


@pytest.mark.parametrize('ballot',[['a','a'],['a','unknown'],['a']])
def test_malformed_ballot_is_rejected(ballot):
    with pytest.raises(ValueError,match='rank each'):
        rank_experiments(['a','b'],[ballot],limit=1)
