"""Pure Python tests — no Odoo runtime needed. Run with pytest."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

import pytest
from gs1 import compute_check_digit, build_gtin13, build_gtin14


class TestComputeCheckDigit:
    """Test compute_check_digit() with known GS1 MOD-10 values."""

    def test_all_zeros(self):
        # digits: [0]*12, all zero → total=0, check=(10-0)%10=0
        assert compute_check_digit('000000000000') == 0

    def test_result_single_digit(self):
        """Check digit must always be 0-9."""
        for i in range(200):
            seq = str(i).zfill(12)
            result = compute_check_digit(seq)
            assert 0 <= result <= 9, f"Got {result} for {seq}"

    def test_known_value_000000000001(self):
        """
        000000000001: 12-digit even-length input.
        even positions (0,2,4,6,8,10): all 0 → odd_sum=0
        odd positions (1,3,5,7,9,11): digits 0,0,0,0,0,1 → even_sum=1
        total = 0 + 1*3 = 3; check = (10-3)%10 = 7
        """
        assert compute_check_digit('000000000001') == 7

    def test_known_value_000000000005(self):
        """
        000000000005: 12-digit even-length input.
        even positions (0,2,4,6,8,10): all 0 → odd_sum=0
        odd positions (1,3,5,7,9,11): digits 0,0,0,0,0,5 → even_sum=5
        total = 0 + 5*3 = 15; check = (10-5)%10 = 5
        """
        assert compute_check_digit('000000000005') == 5

    def test_known_value_000000000100(self):
        """
        000000000100: 12-digit even-length input.
        digits: [0,0,0,0,0,0,0,0,0,1,0,0]
        even positions (0,2,4,6,8,10): 0,0,0,0,0,0 → odd_sum=0
        odd positions (1,3,5,7,9,11): 0,0,0,0,1,0 → even_sum=1
        total = 0 + 1*3 = 3; check = (10-3)%10 = 7
        """
        assert compute_check_digit('000000000100') == 7

    def test_round_trip_gtin13(self):
        """build_gtin13 produces a valid 13-digit string whose last digit equals compute_check_digit."""
        sequences = [
            '000000000000',
            '941941611999',
            '941941612000',
            '941941699999',
            '123456789012',
            '999999999999',
        ]
        for seq in sequences:
            gtin = build_gtin13(seq)
            assert len(gtin) == 13, f"Expected 13 chars, got {len(gtin)} for {seq}"
            assert gtin.isdigit(), f"Non-digit in GTIN-13: {gtin}"
            assert int(gtin[-1]) == compute_check_digit(seq), f"Mismatch for {seq}"

    def test_round_trip_gtin14(self):
        """build_gtin14 produces a valid 14-digit string with indicator '1'."""
        sequences = [
            '000000000000',
            '941941611999',
            '941941612000',
            '123456789012',
        ]
        for seq in sequences:
            gtin = build_gtin14(seq)
            assert len(gtin) == 14, f"Expected 14 chars, got {len(gtin)} for {seq}"
            assert gtin.isdigit(), f"Non-digit in GTIN-14: {gtin}"
            assert gtin[0] == '1', f"Expected indicator '1', got {gtin[0]}"
            # Verify check digit of the 14-digit barcode:
            # strip last char, compute check on first 13 digits
            check = compute_check_digit(gtin[:-1])
            assert int(gtin[-1]) == check, f"Bad check digit in GTIN-14: {gtin}"

    def test_gtin13_different_from_gtin14(self):
        """GTIN-13 and GTIN-14 for same sequence should differ."""
        seq = '941941611999'
        assert build_gtin13(seq) != build_gtin14(seq)

    def test_gtin14_indicator_digit(self):
        """build_gtin14 always prepends '1' as the indicator digit."""
        for seq in ['000000000000', '941941611999', '123456789012']:
            gtin14 = build_gtin14(seq)
            assert gtin14[0] == '1'
            # The 13-digit base (without check) is '1' + sequence
            assert gtin14[1:13] == seq

    def test_raises_on_non_digits(self):
        with pytest.raises(ValueError):
            compute_check_digit('abcdefghijkl')

    def test_raises_on_mixed(self):
        with pytest.raises(ValueError):
            compute_check_digit('94194161199a')

    def test_gtin13_length(self):
        """build_gtin13 always returns exactly 13 characters."""
        assert len(build_gtin13('000000000000')) == 13
        assert len(build_gtin13('999999999999')) == 13

    def test_gtin14_length(self):
        """build_gtin14 always returns exactly 14 characters."""
        assert len(build_gtin14('000000000000')) == 14
        assert len(build_gtin14('999999999999')) == 14
