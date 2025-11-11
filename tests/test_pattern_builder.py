"""
Test cases for chapter pattern builder.

This module tests the pattern builder that converts user-friendly chapter
examples into regex patterns for book ingestion.
"""

import pytest
from src.ui.pattern_builder import build_pattern_from_example, validate_pattern_on_file


class TestPatternGeneration:
    """Test pattern generation from examples."""

    def test_roman_numeral_with_word(self):
        """Test patterns like 'CHAPTER I.' or 'BOOK II'"""
        pattern, desc = build_pattern_from_example("CHAPTER I.")
        # Pattern should match with or without title on same line
        assert pattern == r"^CHAPTER\ [IVXLCDM]+\.(?:\s+.+)?$"
        assert "Roman numerals" in desc

        pattern, desc = build_pattern_from_example("BOOK II")
        # Without period, exact match
        assert pattern == r"^BOOK\ [IVXLCDM]+$"
        assert "Roman numerals" in desc

    def test_arabic_numeral_with_word(self):
        """Test patterns like 'CHAPTER 2' or 'Chapter 1'"""
        pattern, desc = build_pattern_from_example("CHAPTER 2")
        assert pattern == r"^CHAPTER\ \d+$"
        assert "Arabic numerals" in desc

        pattern, desc = build_pattern_from_example("Chapter 1")
        assert pattern == r"^Chapter\ \d+$"
        assert "Arabic numerals" in desc

    def test_bare_roman_numeral_with_period(self):
        """Test bare numeral like 'II.' - should match ONLY bare numerals (no text after)"""
        pattern, desc = build_pattern_from_example("II.")
        assert pattern == r"^[IVXLCDM]+\.$"
        assert "bare numerals only" in desc

    def test_roman_numeral_with_partial_title(self):
        """Test patterns like 'I. A' or 'II. THE' - partial title matching"""
        pattern, desc = build_pattern_from_example("I. A")
        assert pattern == r"^[IVXLCDM]+\.\ A\s+.+$"
        assert "matches lines starting with this pattern" in desc

        pattern, desc = build_pattern_from_example("II. THE")
        assert pattern == r"^[IVXLCDM]+\.\ THE\s+.+$"
        assert "matches lines starting with this pattern" in desc

    def test_wildcard_pattern(self):
        """Test wildcard patterns for spelled-out numbers"""
        pattern, desc = build_pattern_from_example("THE * BOOK")
        assert pattern == r"^THE\ .+\ BOOK$"
        assert "Wildcard pattern" in desc

        pattern, desc = build_pattern_from_example("CHAPTER *")
        assert pattern == r"^CHAPTER\ .+$"
        assert "Wildcard pattern" in desc

    def test_bare_numeral_with_trailing_wildcard(self):
        """Test that 'II. *' or 'II.*' creates optional text pattern"""
        # These should create pattern that matches with or without text
        for example in ["II. *", "II.*", "III. *"]:
            pattern, desc = build_pattern_from_example(example)
            assert pattern == r"^[IVXLCDM]+\.(?:\s+.+)?$"
            assert "with or without title" in desc

    def test_wildcard_with_text_before_numeral(self):
        """Test that 'PART I. *' keeps the wildcard (doesn't normalize)"""
        pattern, desc = build_pattern_from_example("PART I. *")
        assert pattern == r"^PART\ I\.\ .+$"
        assert "Wildcard pattern" in desc

    def test_spelled_out_numbers_give_helpful_error(self):
        """Test that spelled-out numbers return helpful error messages"""
        spelled_examples = [
            "THE FIRST BOOK",
            "BOOK ONE",
            "CHAPTER TWO",
            "THE SECOND CHAPTER",
        ]

        for example in spelled_examples:
            pattern, desc = build_pattern_from_example(example)
            assert pattern == ""
            assert "spelled-out numbers" in desc.lower()
            assert "wildcard" in desc.lower()
            assert "*" in desc

    def test_invalid_examples(self):
        """Test examples with no numbers return appropriate errors"""
        pattern, desc = build_pattern_from_example("CHAPTER")
        assert pattern == ""
        assert "must contain a number" in desc

        pattern, desc = build_pattern_from_example("THE BOOK")
        assert pattern == ""
        assert "must contain a number" in desc

    def test_empty_example(self):
        """Test empty input"""
        pattern, desc = build_pattern_from_example("")
        assert pattern == ""
        assert "No example provided" in desc


class TestPatternValidation:
    """Test pattern validation against actual book files."""

    def test_alice_in_wonderland(self):
        """Test Alice in Wonderland chapter detection"""
        pattern, _ = build_pattern_from_example("CHAPTER I.")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/alice_in_wonderland.txt"
        )

        assert success is True
        assert len(matches) == 12
        assert "CHAPTER I." in matches[0][1]
        assert "CHAPTER XII." in matches[-1][1]

    def test_gullivers_travels(self):
        """Test Gulliver's Travels part detection"""
        pattern, _ = build_pattern_from_example("PART I. A")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/gullivers_travels.txt"
        )

        assert success is True
        assert len(matches) >= 4  # At least 4 parts
        assert "PART" in matches[0][1]

    def test_meditations(self):
        """Test Meditations with wildcard pattern"""
        pattern, _ = build_pattern_from_example("THE * BOOK")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/meditations_marcus_aurelius.txt"
        )

        assert success is True
        assert len(matches) == 12
        assert "FIRST BOOK" in matches[0][1]
        assert "TWELFTH BOOK" in matches[-1][1]

    def test_sherlock_holmes(self):
        """Test Sherlock Holmes with wildcard pattern for chapters with titles"""
        # Use "I.*" to match both bare numerals and titles
        pattern, _ = build_pattern_from_example("I.*")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/sherlock_holmes.txt"
        )

        assert success is True
        # Matches TOC entries with titles plus section markers
        assert len(matches) >= 12
        # Should match titles like "I. A SCANDAL IN BOHEMIA"
        assert any("SCANDAL" in m[1] for m in matches)

    def test_sherlock_holmes_with_wildcard(self):
        """Test that 'II. *' also works for Sherlock Holmes"""
        pattern, _ = build_pattern_from_example("II. *")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/sherlock_holmes.txt"
        )

        assert success is True
        # Now finds both TOC entries with titles AND bare chapter markers
        assert len(matches) >= 12

    def test_the_odyssey(self):
        """Test The Odyssey book detection"""
        pattern, _ = build_pattern_from_example("BOOK I")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/the_odyssey.txt"
        )

        assert success is True
        assert len(matches) == 24
        assert "BOOK I" == matches[0][1]
        assert "BOOK XXIV" in matches[-1][1]

    def test_war_of_the_worlds(self):
        """Test War of the Worlds with wildcard for spelled-out numbers"""
        pattern, _ = build_pattern_from_example("BOOK *")
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/war_of_worlds.txt"
        )

        assert success is True
        assert len(matches) >= 2  # At least BOOK ONE and BOOK TWO

    def test_pattern_validation_requires_minimum_chapters(self):
        """Test that validation requires at least 2 chapters"""
        # Create a pattern that matches very few lines
        pattern = r"^ZZZZZZZ$"
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/alice_in_wonderland.txt"
        )

        assert success is False
        assert "didn't match" in message or "Only found" in message

    def test_pattern_validation_checks_spacing(self):
        """Test that validation checks if matches are properly spaced"""
        # This would match lines too close together (if any matches found)
        pattern = r"^The$"
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/alice_in_wonderland.txt", min_chapters=2
        )

        # Should fail - either no matches or matches too close together
        assert success is False
        assert "didn't match" in message.lower() or "too close" in message.lower()


class TestEdgeCases:
    """Test edge cases and user mistakes."""

    def test_normalization_cases(self):
        """Test that bare vs wildcard patterns are different"""
        # Bare numeral patterns (exact match)
        bare_patterns = ["II.", "III."]
        for ex in bare_patterns:
            pattern = build_pattern_from_example(ex)[0]
            assert pattern == r"^[IVXLCDM]+\.$"

        # Wildcard patterns (optional text)
        wildcard_patterns = ["II. *", "II.*", "III. *"]
        for ex in wildcard_patterns:
            pattern = build_pattern_from_example(ex)[0]
            assert pattern == r"^[IVXLCDM]+\.(?:\s+.+)?$"

    def test_case_sensitivity(self):
        """Test that patterns are case-sensitive where needed"""
        pattern1, _ = build_pattern_from_example("CHAPTER I")
        pattern2, _ = build_pattern_from_example("Chapter I")

        assert pattern1 != pattern2
        assert "CHAPTER" in pattern1
        assert "Chapter" in pattern2

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly"""
        pattern1, _ = build_pattern_from_example("  CHAPTER I.  ")
        pattern2, _ = build_pattern_from_example("CHAPTER I.")

        assert pattern1 == pattern2

    def test_complex_wildcard_patterns(self):
        """Test complex wildcard patterns"""
        pattern, _ = build_pattern_from_example("THE * BOOK OF *")
        assert pattern == r"^THE\ .+\ BOOK\ OF\ .+$"

    def test_arabic_and_roman_mix(self):
        """Test that Arabic and Roman numerals generate different patterns"""
        pattern_roman, _ = build_pattern_from_example("CHAPTER II")
        pattern_arabic, _ = build_pattern_from_example("CHAPTER 2")

        assert pattern_roman != pattern_arabic
        assert "[IVXLCDM]+" in pattern_roman
        assert r"\d+" in pattern_arabic

    def test_part_pattern_with_wildcard(self):
        """Test PART I.* normalization (Gulliver's Travels use case)"""
        # User enters 'PART I.*' - should normalize and work
        pattern, desc = build_pattern_from_example("PART I.*")
        assert pattern == r"^PART\ [IVXLCDM]+\.(?:\s+.+)?$"
        assert "Roman numerals" in desc

        # Validate against actual file
        success, message, matches = validate_pattern_on_file(
            pattern, "DATA/gullivers_travels.txt"
        )
        assert success is True
        assert len(matches) >= 4

    def test_chapter_pattern_with_wildcard(self):
        """Test CHAPTER I.* normalization (Alice use case)"""
        # Both 'CHAPTER I.' and 'CHAPTER I.*' should work
        pattern1, _ = build_pattern_from_example("CHAPTER I.")
        pattern2, _ = build_pattern_from_example("CHAPTER I.*")

        # Should generate the same pattern
        assert pattern1 == pattern2
        assert pattern1 == r"^CHAPTER\ [IVXLCDM]+\.(?:\s+.+)?$"

    def test_word_numeral_period_patterns(self):
        """Test that WORD NUMERAL. patterns work with or without titles"""
        test_cases = [
            "CHAPTER I.",
            "PART II.",
            "SECTION III.",
            "ACT IV.",
            "SCENE V.",
        ]

        for example in test_cases:
            pattern, desc = build_pattern_from_example(example)
            # Should generate optional continuation pattern
            assert "(?:\\s+.+)?$" in pattern
            assert "with or without title" in desc.lower()

    def test_arabic_with_period_patterns(self):
        """Test patterns with Arabic numerals and periods"""
        # 'Chapter 1.' should also get optional continuation
        pattern, desc = build_pattern_from_example("Chapter 1.")
        assert pattern == r"^Chapter\ \d+\.(?:\s+.+)?$"
        assert "Arabic numerals" in desc

        # Test various formats
        test_cases = [
            ("Section 1.", r"^Section\ \d+\.(?:\s+.+)?$"),
            ("Part 5.", r"^Part\ \d+\.(?:\s+.+)?$"),
            ("Act 3.", r"^Act\ \d+\.(?:\s+.+)?$"),
        ]

        for example, expected_pattern in test_cases:
            pattern, _ = build_pattern_from_example(example)
            assert pattern == expected_pattern

    def test_bare_arabic_numeral_with_period(self):
        """Test bare Arabic numerals like '1.' or '2.'"""
        # Without wildcard - matches ONLY bare numerals
        pattern, desc = build_pattern_from_example("2.")
        assert pattern == r"^\d+\.$"
        assert "bare numerals only" in desc

        # With wildcard - matches with or without title
        pattern2, desc2 = build_pattern_from_example("2.*")
        assert pattern2 == r"^\d+\.(?:\s+.+)?$"
        assert "with or without title" in desc2

    def test_mixed_case_patterns(self):
        """Test patterns with mixed case (user's actual input)"""
        # Lowercase roman numerals are not supported (uppercase only)
        pattern1, desc1 = build_pattern_from_example("chapter i.")
        assert pattern1 == ""  # Should fail - lowercase roman numerals not detected
        assert "must contain a number" in desc1

        # Mixed case with uppercase Roman numeral works
        pattern2, _ = build_pattern_from_example("Chapter I.")
        assert "Chapter" in pattern2
        assert "[IVXLCDM]+" in pattern2

        # All uppercase works
        pattern3, _ = build_pattern_from_example("CHAPTER I.")
        assert "CHAPTER" in pattern3
        assert "[IVXLCDM]+" in pattern3

        # Mixed and uppercase generate different patterns
        assert pattern2 != pattern3

    def test_pattern_with_colon(self):
        """Test patterns with colons (less common but valid)"""
        # Some books use 'CHAPTER I:' instead of 'CHAPTER I.'
        pattern, desc = build_pattern_from_example("CHAPTER I:")
        # Should still work - colon is preserved in pattern
        assert "CHAPTER" in pattern
        assert "[IVXLCDM]+" in pattern
        assert ":" in pattern
        # Exact match expected (no period, so no optional continuation)
        assert pattern == r"^CHAPTER\ [IVXLCDM]+:$"


class TestUserExperience:
    """Test user experience and helpful error messages."""

    def test_helpful_error_for_common_mistake(self):
        """Test that common mistakes get helpful error messages"""
        # User copies full chapter name with spelled-out number
        pattern, desc = build_pattern_from_example("THE FIRST BOOK")

        assert pattern == ""
        assert "spelled-out numbers" in desc.lower()
        assert "THE * BOOK" in desc  # Suggests the correct pattern

    def test_description_clarity(self):
        """Test that pattern descriptions are clear and informative"""
        test_cases = [
            ("CHAPTER I.", "Roman numerals"),
            ("CHAPTER 2", "Arabic numerals"),
            ("THE * BOOK", "Wildcard pattern"),
            ("II.", "bare numerals only"),
            ("II.*", "with or without title"),
        ]

        for example, expected_in_desc in test_cases:
            _, desc = build_pattern_from_example(example)
            assert expected_in_desc.lower() in desc.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
