"""Validate this specific failed phase before continuing its ranked queue."""
from sera.storage import content_hash
from sera.kernel_swarm_plan import rank_experiments


def validate_plan(state):
    if state['calls'] != 32 or state['implementations'] != 1 or len(state['rounds']) != 1:
        raise ValueError('Changed spent budget')
    if state['max_rounds'] != 6 or state['max_model_calls'] != 108 or state['batch_size'] != 3:
        raise ValueError('Changed original limits')
    batch = state['rounds'][0]
    if len(batch['roles']) != 15 or len(set(batch['roles'])) != 15:
        raise ValueError('Incomplete roster')
    if batch['board_hash'] != content_hash(batch['board']):
        raise ValueError('Changed proposal board')
    ballots = batch['ballots']
    if len(ballots) != 15 or any(b['status'] != 'received' for b in ballots):
        raise ValueError('Incomplete rankings')
    order = rank_experiments([b['experiment_id'] for b in batch['board']],
                            [b['ranking'] for b in ballots], limit=3)
    if batch['experiment_order'] != order or state['pending'] != order[1:]:
        raise ValueError('Changed ranked order')
    attempts = batch['implementations']
    if (len(attempts) != 1 or attempts[0]['experiment_id'] != order[0] or
            attempts[0]['status'] != 'failed' or
            not attempts[0]['error'].startswith('TimeoutExpired:')):
        raise ValueError('Unexpected prior implementation outcome')
