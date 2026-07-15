def clamp(value: float, min_value: float = 0.01, max_value: float = 0.99) -> float:
    return max(min_value, min(max_value, value))


def update_mastery(
    prior: float,
    correct: bool,
    p_learn: float = 0.15,
    p_slip: float = 0.1,
    p_guess: float = 0.2,
) -> float:
    if correct:
        numerator = prior * (1 - p_slip)
        denominator = numerator + (1 - prior) * p_guess
    else:
        numerator = prior * p_slip
        denominator = numerator + (1 - prior) * (1 - p_guess)

    posterior = numerator / denominator if denominator else prior
    posterior = posterior + (1 - posterior) * p_learn
    return clamp(posterior)
