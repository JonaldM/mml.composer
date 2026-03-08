"""
GS1 MOD-10 check digit computation.

Pure Python — no Odoo dependency. Import freely from models and tests.

Reference: https://www.gs1.org/services/how-calculate-check-digit-manually
"""


def compute_check_digit(sequence: str) -> int:
    """
    Compute the GS1 MOD-10 check digit for a sequence string.

    Args:
        sequence: 12-digit string for GTIN-13, or 13-digit string for GTIN-14.
                  Must contain only ASCII digits.

    Returns:
        Single integer 0-9 representing the check digit.

    Raises:
        ValueError: if sequence contains non-digit characters.
    """
    if not sequence.isdigit():
        raise ValueError(f"sequence must contain only digits, got: {sequence!r}")

    digits = [int(d) for d in sequence]
    n = len(digits)

    if n % 2 == 0:
        # Even-length input (e.g. 12 digits for GTIN-13):
        # positions 0,2,4,... multiplied by 1
        # positions 1,3,5,... multiplied by 3
        odd_sum = sum(digits[i] for i in range(0, n, 2))
        even_sum = sum(digits[i] for i in range(1, n, 2))
        total = odd_sum + even_sum * 3
    else:
        # Odd-length input (e.g. 13 digits for GTIN-14):
        odd_sum = sum(digits[i] for i in range(0, n, 2))
        even_sum = sum(digits[i] for i in range(1, n, 2))
        total = odd_sum * 3 + even_sum

    return (10 - (total % 10)) % 10


def build_gtin13(sequence: str) -> str:
    """Build a full GTIN-13 string from a 12-digit sequence."""
    return sequence + str(compute_check_digit(sequence))


def build_gtin14(sequence: str) -> str:
    """
    Build a GTIN-14 from a 12-digit sequence.
    Indicator digit is '1' (standard outer carton indicator).
    """
    base = '1' + sequence  # 13 digits
    return base + str(compute_check_digit(base))
