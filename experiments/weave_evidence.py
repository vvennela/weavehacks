"""Benchmark answer-key adapter for the installed scoped Weave reader."""

from benchmarks.grade import grade_case
from sera.weave_evidence import IDENTITY_FIELDS, QUERY_IDS, RECORDED_OPS, WeaveEvidenceError, _diagnosis
from sera.weave_evidence import WeaveEvidenceReader as ScopedWeaveEvidenceReader


class WeaveEvidenceReader(ScopedWeaveEvidenceReader):
    def __init__(self, client, trace_id, *, evaluation_cases=None):
        super().__init__(client, trace_id, evaluation_cases=evaluation_cases, case_evaluator=grade_case)
