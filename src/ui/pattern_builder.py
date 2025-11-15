"""
Build regex pattern from a single chapter example.
"""

import re
from pathlib import Path
import pdfplumber


def build_pattern_from_example(example: str) -> tuple[str, str]:
    """
    Convert user's chapter example into regex pattern.

    Examples:
        "CHAPTER 2" -> Matches CHAPTER 1, CHAPTER 2, CHAPTER 3, ...
        "BOOK II" -> Matches BOOK I, BOOK II, BOOK III, ...
        "II." -> Matches I., II., III., ...
        "1. Title" -> Matches 1. Title, 2. Another, ...
        "THE * BOOK" -> Matches THE FIRST BOOK, THE SECOND BOOK, ...

    Returns:
        (regex_pattern, description)
    """
    example = example.strip()

    if not example:
        return "", "No example provided"

    # Handle wildcards after bare numerals:
    # "I.*" or "I. *" → User wants to match with OR without titles (e.g., "I. TITLE" or just "I.")
    # "I." → User wants ONLY bare numerals (e.g., just "I.", not "I. TITLE")
    # This distinction is crucial for books like:
    #   - Sherlock Holmes: Use "I.*" to match "I. A SCANDAL IN BOHEMIA"
    #   - War of the Worlds: Use "I." to match only bare "I." (title on next line)

    # Check if it's a bare numeral with trailing wildcard
    bare_numeral_with_wildcard = (
        re.search(r"^[IVXLCDM]+\.\s*\*\s*$", example) or
        re.search(r"^\d+\.\s*\*\s*$", example)
    )

    if bare_numeral_with_wildcard:
        # User wants optional text after numeral - strip wildcard, set flag
        example = re.sub(r"\.\s*\*\s*$", ".", example)
        make_text_optional = True
    else:
        make_text_optional = False

    # For word+numeral patterns, normalize .* (e.g., "CHAPTER I.*" → "CHAPTER I.")
    if re.search(r"\w+\s+[IVXLCDM]+\.\*\s*$", example) or re.search(
        r"\w+\s+\d+\.\*\s*$", example
    ):
        example = re.sub(r"\.\*\s*$", ".", example)

    # Check for wildcard pattern (*)
    if "*" in example:
        # Replace * with pattern that matches one or more words (including spaces)
        pattern = example.replace("*", r".+")
        # Escape special regex chars except our pattern
        pattern = re.escape(pattern)
        # Restore the .+ pattern
        pattern = pattern.replace(r"\.\+", r".+")
        pattern = f"^{pattern}$"
        desc = f"Wildcard pattern (based on '{example}')"
        return pattern, desc

    # Detect and replace the number/numeral
    # Try Arabic numerals first (more specific)
    arabic_match = re.search(r"\d+", example)
    if arabic_match:
        # Replace ONLY the number with pattern
        pattern = re.sub(r"\d+", "___ARABIC___", example)
        # Escape the whole thing
        pattern = re.escape(pattern)
        # Put back the pattern
        pattern = pattern.replace("___ARABIC___", r"\d+")
        desc = f"Pattern with Arabic numerals (based on '{example}')"

    # Try Roman numerals (must be standalone word, typically 1-5 chars)
    elif re.search(r"\b([IVXLCDM]{1,5})\b", example):
        roman_match = re.search(r"\b([IVXLCDM]{1,5})\b", example)
        # Replace ONLY the Roman numeral with pattern, keep rest as-is
        numeral = roman_match.group(1)
        pattern = example.replace(numeral, "___ROMAN___")
        # Escape the whole thing
        pattern = re.escape(pattern)
        # Put back the pattern
        pattern = pattern.replace("___ROMAN___", "[IVXLCDM]+")
        desc = f"Pattern with Roman numerals (based on '{example}')"

    else:
        # Check if it contains spelled-out numbers
        spelled_numbers = [
            "ONE",
            "TWO",
            "THREE",
            "FOUR",
            "FIVE",
            "SIX",
            "SEVEN",
            "EIGHT",
            "NINE",
            "TEN",
            "FIRST",
            "SECOND",
            "THIRD",
            "FOURTH",
            "FIFTH",
            "SIXTH",
            "SEVENTH",
            "EIGHTH",
            "NINTH",
            "TENTH",
            "ELEVENTH",
            "TWELFTH",
        ]
        if any(num in example.upper() for num in spelled_numbers):
            return (
                "",
                f"Pattern '{example}' contains spelled-out numbers. Use wildcard: replace the number with * (e.g., 'THE * BOOK' or 'CHAPTER *')",
            )

        return (
            "",
            f"Example '{example}' must contain a number (2, 3, ...) or Roman numeral (I, II, III, ...)",
        )

    # Add line start anchor, but make end flexible if example looks incomplete
    # Rules:
    # 1. If example ends with common starter words (A, THE, etc.) → add continuation
    # 2. If example is JUST numeral + period (like "II.") → add continuation
    # 3. If example has word + numeral + period (like "CHAPTER II." or "PART I.") → add continuation
    # 4. If example has period + space + text (like "II. THE") → partial match
    # 5. If example has word + numeral but NO period (like "BOOK I") → exact match

    if re.search(r"\b(A|THE|AN|OF|IN|ON|TO|FOR)\s*$", example, re.IGNORECASE):
        # Case 1: Ends with starter word
        pattern = f"^{pattern}\\s+.+$"
        desc += " (matches lines starting with this pattern)"
    elif re.search(r"^\s*[IVXLCDM]+\.\s*$", example) or re.search(
        r"^\s*\d+\.\s*$", example
    ):
        # Case 2: Just a bare numeral with period (like "II." or "2.")
        # Check if user specified wildcard (meaning they want optional text)
        if make_text_optional:
            # User entered "I.*" - match with or without title
            pattern = f"^{pattern}(?:\\s+.+)?$"
            desc += " (matches with or without title on same line)"
        else:
            # User entered "I." - match ONLY bare numerals
            pattern = f"^{pattern}$"
            desc += " (matches bare numerals only)"
    elif re.search(r"\w+\s+[IVXLCDM]+\.\s*$", example) or re.search(
        r"\w+\s+\d+\.\s*$", example
    ):
        # Case 3: Word + numeral + period (like "CHAPTER II." or "PART I.")
        # Make continuation optional to handle both "CHAPTER I." alone and "PART I. TITLE"
        pattern = f"^{pattern}(?:\\s+.+)?$"
        desc += " (matches with or without title on same line)"
    elif re.search(r"\.\s+\w", example):
        # Case 4: Has period + space + word already
        pattern = f"^{pattern}"
        desc += " (partial match - will match lines starting with this)"
    else:
        # Case 5: Exact match (like "BOOK I" without period)
        pattern = f"^{pattern}$"

    return pattern, desc


def validate_pattern_on_file(
    pattern: str, file_path: str, min_chapters: int = 2
) -> tuple[bool, str, list]:
    """
    Test pattern against file.

    Returns:
        (success, message, sample_matches)
        sample_matches: [(line_number, text), ...]
    """
    try:
        path = Path(file_path)
        file_extension = path.suffix.lower()

        # Handle PDF files
        if file_extension == ".pdf":
            # Extract text from PDF
            text_content = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)

            # Combine all pages and split into lines
            full_text = "\n".join(text_content)
            lines = full_text.split("\n")
        else:
            # Handle text files
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # Skip first 50 lines (typically headers)
        start_line = min(50, len(lines) // 10)

        matches = []
        for i in range(start_line, len(lines)):
            stripped = lines[i].strip()
            if re.match(pattern, stripped):
                matches.append((i + 1, stripped))

        if not matches:
            return False, "Pattern didn't match any lines", []

        if len(matches) < min_chapters:
            return (
                False,
                f"Only found {len(matches)} match(es). Need at least {min_chapters}.",
                matches,
            )

        # Check spacing - chapters should span significant portion of file
        line_numbers = [m[0] for m in matches]
        span = line_numbers[-1] - line_numbers[0]
        total_lines = len(lines)

        if span < total_lines * 0.1:
            return (
                False,
                f"Matches are too close together ({span} lines). May not be actual chapters.",
                matches,
            )

        # Success!
        message = f"Found {len(matches)} chapters\n"
        message += f"  First: Line {matches[0][0]} - {matches[0][1]}\n"
        message += f"  Last: Line {matches[-1][0]} - {matches[-1][1]}"

        return True, message, matches

    except Exception as e:
        return False, f"Error: {str(e)}", []
