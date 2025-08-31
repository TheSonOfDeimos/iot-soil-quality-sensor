import array

def percentile(data, q) -> float :
    if not isinstance(data, array.array):
        raise TypeError("data must be array.array")
    n = len(data)
    if n == 0:
        raise ValueError("empty array")

    values = sorted(data)
    rank = (q / 100) * (n - 1)
    i = int(rank)
    frac = rank - i
    if i + 1 < n:
        return values[i] + (values[i+1] - values[i]) * frac
    else:
        return float(values[i])
    
def average(data : array.array) -> float :
    if not isinstance(data, array.array):
        raise TypeError("data must be array.array")
    n = len(data)
    if n == 0:
        raise ValueError("empty array")
    return sum(data) / n

def percentage_in_bounds(value, lower, upper) -> float :
    if lower == upper:
        raise ValueError("lower and upper bounds must differ")
    return min(100.0, max(0.0, (value - lower) * 100.0 / (upper - lower)))
