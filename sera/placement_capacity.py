"""Source-qualified capacity comparison, never invented unquantized latency."""


def capacity_evidence(selected_plan, rejected, plans, placement_report):
    unavailable = dict(established=False, reason='no-matching-unquantized-fit-rejection',
                       measured_memory_savings_bytes=None)
    gates = placement_report.get('joint', {}).get('gates', {})
    if (placement_report.get('decision', {}).get('outcome') != 'safe-placement'
            or set(gates) != {service.model_id for service in selected_plan.services}
            or not all(gate.get('passed') is True for gate in gates.values())
            or placement_report.get('shared_runtime', {}).get('errors')):
        return unavailable | dict(reason='selected-pair-did-not-pass')
    for rejection in rejected:
        if rejection.get('reason') != 'estimated-memory-does-not-fit':
            continue
        original = plans[rejection['plan_id']]
        if (original.physical_gpu_bytes != selected_plan.physical_gpu_bytes
                or original.declared_budget_bytes != selected_plan.declared_budget_bytes):
            continue
        old_services = {service.model_id:service for service in original.services}
        changed = {}
        matched = True
        for service in selected_plan.services:
            previous = old_services.get(service.model_id)
            if (previous is None or previous.revision != service.revision
                    or previous.allocation_bytes != service.allocation_bytes
                    or previous.gpu_index != service.gpu_index or previous.constraints != service.constraints):
                matched = False
                break
            before, after = previous.configuration.model_dump(), service.configuration.model_dump()
            differences = {key for key in before if before[key] != after[key]}
            if differences:
                if differences != {'quantization'} or before['quantization'] is not None or after['quantization'] != 'fp8_per_tensor':
                    matched = False
                    break
                changed[service.model_id] = dict(before=None, after='fp8_per_tensor')
        if not matched or not changed:
            continue
        peak = placement_report.get('shared_runtime', {}).get('sampled_peak_memory_mib')
        if type(peak) is not int or not 0 < peak*1024**2 <= selected_plan.declared_budget_bytes:
            return unavailable | dict(reason='measured-device-memory-unavailable')
        return dict(established=True, selected_plan_id=selected_plan.plan_hash,
            unquantized_plan_id=original.plan_hash, changed_weight_precision=changed,
            unquantized_failure_basis='deterministic-estimate-not-measured',
            unquantized_fit_check=rejection['fit_check'],
            quantized_outcome='measured-safe-placement', measured_quantized_peak_bytes=peak*1024**2,
            declared_budget_bytes=selected_plan.declared_budget_bytes,
            physical_gpu_bytes=selected_plan.physical_gpu_bytes,
            measured_declared_headroom_bytes=selected_plan.declared_budget_bytes-peak*1024**2,
            measured_memory_savings_bytes=None,
            memory_accounting=placement_report.get('memory_accounting', 'per-service'),
            allocation_scope=('Configured vLLM budgets, not separately verified hard caps; '
                'no claim that every possible BF16 allocation fails the total device budget'
                if placement_report.get('memory_accounting') == 'total-device' else 'Per-service sampled hard caps'),
            scope='Measured passing quantized pair versus otherwise-matching BF16 plan rejected by the supplied memory estimate; '
                  'no measured BF16 joint latency or memory savings, no global-optimality claim')
    return unavailable
