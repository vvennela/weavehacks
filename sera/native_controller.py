"""Service-owned research process; credentials never enter its request file."""
import json
import sys
from pathlib import Path

from .native_optimizer import optimize_native
from .native_worker import _parent_watchdog
from .storage import save_json


def main():
    _parent_watchdog()
    folder = Path(sys.argv[1])
    request = json.loads((folder / 'request.json').read_text())
    if 'rag_request' in request:
        from .rag_intake import IntakeNeedsInput, prepare_rag
        try:
            compiled = prepare_rag(request['rag_request'], folder)
        except IntakeNeedsInput as error:
            questions = error.questions
            from .native_trace import trace_native_job
            traced = trace_native_job(project=request['rag_request']['project'], run=lambda: {
                'status': 'needs-input', 'question_count': len(questions)})
            save_json(folder / 'needs-input.json', {'questions': questions, 'trace': traced['trace']})
            return
        request = {'profile': compiled['profile'], 'project': request['rag_request']['project']}
    research = folder / 'research'
    optimize_native(profile=request['profile'], output_dir=research,
                    project=request['project'], resume=(research / 'ledger.sqlite3').exists())


if __name__ == '__main__':
    main()
