from math import inf


def route_cost(order: list[int], matrix: list[list[float]]) -> float:
    return sum(matrix[a][b] for a, b in zip(order, order[1:], strict=False))


def nearest_neighbor_order(matrix: list[list[float]], stop_count: int) -> list[int]:
    """Construct 0=start, 1..n=stops, n+1=end route using duration matrix."""
    end = stop_count + 1
    remaining = set(range(1, end))
    order = [0]
    current = 0
    while remaining:
        nxt = min(remaining, key=lambda index: matrix[current][index])
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt
    order.append(end)
    return order


def two_opt(order: list[int], matrix: list[list[float]]) -> list[int]:
    """Improve a closed/open route by reversing interior subsequences until stable."""
    result = order[:]
    improved = True
    while improved:
        improved = False
        best_cost = route_cost(result, matrix)
        for i in range(1, len(result) - 2):
            for k in range(i + 1, len(result) - 1):
                candidate = result[:i] + list(reversed(result[i:k + 1])) + result[k + 1:]
                cost = route_cost(candidate, matrix)
                if cost + 1e-9 < best_cost:
                    result, best_cost, improved = candidate, cost, True
    return result


def optimize(matrix: list[list[float]], stop_count: int) -> dict:
    expected = stop_count + 2
    if len(matrix) != expected or any(len(row) != expected for row in matrix):
        raise ValueError("Routing matrix dimensions do not match start, stops, and end")
    if any(value is None or value < 0 or value == inf for row in matrix for value in row):
        raise ValueError("Routing matrix contains an unreachable or invalid leg")
    baseline = [0, *range(1, stop_count + 1), expected - 1]
    optimized = two_opt(nearest_neighbor_order(matrix, stop_count), matrix)
    baseline_cost = route_cost(baseline, matrix)
    optimized_cost = route_cost(optimized, matrix)
    return {"baseline_order": baseline, "optimized_order": optimized, "baseline_duration_seconds": baseline_cost, "optimized_duration_seconds": optimized_cost, "duration_saved_seconds": baseline_cost - optimized_cost, "duration_saved_percentage": ((baseline_cost-optimized_cost)/baseline_cost*100 if baseline_cost > 0 else None), "method": "nearest-neighbor construction + 2-opt local search; heuristic, not globally optimal"}
