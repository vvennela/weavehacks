"""Operator-owned W&B inference. Credentials exist only on the control service."""

from .agent import AGENT_MODEL, PROVIDER_URL, WandbAgent, request_schema
from .storage import content_hash


class ManagedWandbAgent(WandbAgent):
    """Use the hosted decoder's flat schema and unchanged local validators.

    W&B's current grammar compiler rejects the conditional root union with an
    empty integer range. Fields, bounds, and enums still constrain the wire
    response; Sera validates all action/role/value dependencies before use.
    """

    def __init__(self, *, project, model=AGENT_MODEL):
        super().__init__(project=project, model=model)
        self.endpoint_fingerprint = content_hash({
            'endpoint': PROVIDER_URL, 'transport': 'sera-managed-wandb-flat-root-v1'})

    def wire_schema(self, role, evidence):
        schema = request_schema(role, evidence)
        if role == 'proposal':
            schema.pop('anyOf', None)
        return schema

    def fork(self):
        return ManagedWandbAgent(project=self.project, model=self.model)
