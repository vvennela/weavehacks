"""Conservative memory arithmetic. All quantities are bytes, not GiB."""


def _nonnegative_integer(name, value):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def estimate_memory(*, parameter_count, weight_bytes, layers, kv_heads, head_dim,
                    tokens, sequences, kv_bytes, workspace_bytes):
    """Estimate weights and full-attention KV storage; workspace is supplied."""
    for name, value in locals().copy().items():
        _nonnegative_integer(name, value)
    weights = parameter_count * weight_bytes
    cache = 2 * layers * kv_heads * head_dim * tokens * sequences * kv_bytes
    return {"weights_bytes": weights, "kv_bytes": cache,
            "workspace_bytes": workspace_bytes,
            "total_bytes": weights + cache + workspace_bytes}


def fits_memory(*, required_bytes, budget_bytes, reserve_bytes):
    for name, value in locals().copy().items():
        _nonnegative_integer(name, value)
    return required_bytes + reserve_bytes <= budget_bytes


def combined_allocations_fit(allocations, *, declared_bytes, physical_bytes, reserve_bytes):
    required = sum(_nonnegative_integer("allocation", value) for value in allocations)
    return (fits_memory(required_bytes=required, budget_bytes=declared_bytes,
                        reserve_bytes=reserve_bytes)
            and fits_memory(required_bytes=required, budget_bytes=physical_bytes,
                            reserve_bytes=reserve_bytes))
