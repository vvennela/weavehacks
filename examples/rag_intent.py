"""Use a document collection connected to a local, operator-managed Sera service."""
import argparse
import json
import os
from dataclasses import asdict

from sera import Optimize, SeraNeedsInput


def main():
    parser = argparse.ArgumentParser(description='Sera: the autonomous auto-research harness for inference')
    parser.add_argument('workload', help='Describe the document question-answering workload')
    parser.add_argument('--documents', required=True, help='Connected document collection name')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8765')
    parser.add_argument('--request-id', required=True, help='Reuse this ID to reconnect to the same job')
    parser.add_argument('--question', action='append', default=[], help='Ask the returned pipeline a new question')
    args = parser.parse_args()
    try:
        result = Optimize(args.workload, documents=args.documents,
                          api_key=os.environ['SERA_ACCESS_KEY'], endpoint=args.endpoint,
                          request_id=args.request_id)
    except SeraNeedsInput as error:
        print(json.dumps({'status': 'needs-input', 'questions': error.questions}, indent=2))
        return
    print(json.dumps(asdict(result), indent=2))
    if args.question:
        with result.load() as pipeline:
            for question in args.question:
                print(json.dumps({'question': question, **pipeline.answer(question)}))


if __name__ == '__main__':
    main()
