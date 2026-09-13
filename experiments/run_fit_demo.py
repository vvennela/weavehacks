"""Run the pinned large-model deployment demo on the supplied Linux GPU."""

import argparse
from pathlib import Path

import sera
from benchmarks.grade import SYSTEM_PROMPT, grade_case, load_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--provider-check", required=True)
    parser.add_argument("--output-dir", required=True, help="A new evidence directory")
    parser.add_argument("--priority", choices=["latency", "throughput", "memory"], default="throughput")
    parser.add_argument("--interactive", action="store_true", help="Keep the returned runner for live prompts")
    args = parser.parse_args()

    import weave

    cases = load_cases(Path(__file__).resolve().parents[1] / "benchmarks" / "easy_cases.json")
    by_prompt = {case["prompt"]: case for case in cases}
    prompts = [[{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case["prompt"]}] for case in cases]

    def evaluate_answer(prompt, output):
        return grade_case(by_prompt[prompt[-1]["content"]], output)["passed"]

    client = weave.init(args.project)

    @weave.op
    def run_demo():
        with sera.optimize(
            models=["Qwen/Qwen2.5-72B-Instruct"], prompts=prompts,
            output_dir=args.output_dir,
            evaluation=evaluate_answer, evaluation_version="sera-easy-strict-json-v1",
            constraints=sera.Constraints(quality_floor=0.99),
            objective=sera.Objective(priority=args.priority),
            agent=sera.WandbAgent(project=args.project),
            provider_check=args.provider_check,
        ) as result:
            result.report["workload_name"] = "easy-json-system-v1"
            result.report["evaluation_cases"] = cases
            result.report["weave_url"] = weave.get_current_call().ui_url
            if result.models:
                response = result.models[0].generate(prompts[0])
                result.report["post_return_probe"] = response.to_dict()
                result.report["post_return_task_passed"] = evaluate_answer(prompts[0], response.text)
            result._save()
            result.print_summary()
            if args.interactive and result.models:
                print("Runner is ready. These new prompts are not part of the quality score. Blank input stops it.")
                while True:
                    try:
                        prompt = input("Prompt: ").strip()
                    except EOFError:
                        break
                    if not prompt:
                        break
                    print(result.models[0].generate(prompt).text)
        return result.report

    try:
        report = run_demo()
    finally:
        client.flush()
    return 0 if report.get("task_quality_verified") and report.get("post_return_task_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
