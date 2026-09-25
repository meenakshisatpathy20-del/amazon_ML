"""
Compiler-Design Lexer for Business Entity Resolution.

Pipeline position:

RAW BUSINESS NAME / ADDRESS
        ↓
      LEXER
        ↓
  TOKEN CLASSIFICATION
        ↓
 SYMBOL TABLE / PARSER
        ↓
 STRUCTURED ENTITY IR

Important:
- Unicode-safe
- Preserves Hindi, Tamil, Kannada and other scripts
- Preserves numbers
- Identifies legal suffixes
- Identifies road types
- Does NOT throw away non-Latin text
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import List


# ============================================================
# TOKEN TYPES
# ============================================================

class TokenType(Enum):
    WORD = "WORD"
    NUMBER = "NUMBER"
    HOUSE_NUMBER = "HOUSE_NUMBER"
    POSTAL_CODE = "POSTAL_CODE"
    LEGAL_SUFFIX = "LEGAL_SUFFIX"
    ROAD_TYPE = "ROAD_TYPE"
    PUNCTUATION = "PUNCTUATION"
    OTHER = "OTHER"


# ============================================================
# TOKEN
# ============================================================

@dataclass
class Token:
    value: str
    token_type: TokenType

    def __repr__(self):
        return f"Token(value={self.value!r}, type={self.token_type.value})"


# ============================================================
# LEXER
# ============================================================

class Lexer:
    """
    Unicode-safe lexical analyzer.

    The lexer converts raw business names and addresses into
    meaningful lexical tokens.

    Example:

        "1056-1060 BELDEN AVE, AKRON, OH"

    becomes approximately:

        1056-1060 -> HOUSE_NUMBER
        BELDEN    -> WORD
        AVE       -> ROAD_TYPE
        AKRON     -> WORD
        OH        -> WORD

    Multilingual example:

        "रेड वेंचर्स प्राइवेट लिमिटेड"

    remains:

        रेड
        वेंचर्स
        प्राइवेट
        लिमिटेड

    instead of being discarded.
    """

    # --------------------------------------------------------
    # Legal suffixes
    # --------------------------------------------------------

    LEGAL_SUFFIXES = {
        "inc",
        "inc.",
        "incorporated",

        "ltd",
        "ltd.",
        "limited",

        "pvt",
        "pvt.",
        "private",

        "llc",
        "l.l.c",

        "plc",

        "llp",

        "corp",
        "corp.",
        "corporation",

        "co",
        "co.",
        "company",
    }

    # --------------------------------------------------------
    # Road types
    # --------------------------------------------------------

    ROAD_TYPES = {
        "rd",
        "rd.",
        "road",

        "st",
        "st.",
        "street",

        "ave",
        "ave.",
        "avenue",

        "blvd",
        "blvd.",
        "boulevard",

        "dr",
        "dr.",
        "drive",

        "ln",
        "ln.",
        "lane",

        "ct",
        "ct.",
        "court",

        "cir",
        "cir.",
        "circle",

        "hwy",
        "hwy.",
        "highway",

        "pkwy",
        "pkwy.",
        "parkway",

        "pl",
        "pl.",
        "place",

        "terr",
        "terr.",
        "terrace",

        "way",

        "trl",
        "trl.",
        "trail",

        "sq",
        "sq.",
        "square",
    }

    # --------------------------------------------------------
    # Common address abbreviations
    # --------------------------------------------------------

    ADDRESS_ABBREVIATIONS = {
        "apt",
        "apt.",

        "fl",
        "fl.",

        "ste",
        "ste.",

        "hno",
        "h.no",
        "h.no.",

        "no",
        "no.",

        "po",
        "p.o",
        "p.o.",

        "pobox",
        "po-box",
        "po box",

        "blk",
        "blk.",

        "bldg",
        "bldg.",

        "rm",
        "rm.",

        "unit",

        "floor",
        "block",
        "building",
    }

    # --------------------------------------------------------
    # Constructor
    # --------------------------------------------------------

    def __init__(self):
        # Symbol-table-like dictionaries.
        #
        # We keep these inside the lexer as lexical lookup
        # tables. The dedicated SymbolTable will later perform
        # canonicalization.
        self.legal_suffixes = {
            value.casefold()
            for value in self.LEGAL_SUFFIXES
        }

        self.road_types = {
            value.casefold()
            for value in self.ROAD_TYPES
        }

        self.address_abbreviations = {
            value.casefold()
            for value in self.ADDRESS_ABBREVIATIONS
        }

    # ========================================================
    # UNICODE NORMALIZATION
    # ========================================================

    def normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode without destroying non-Latin scripts.

        NFKD decomposes characters such as:

            é -> e + accent

        We remove combining marks only.

        IMPORTANT:
        We do NOT convert the entire string to ASCII.

        Therefore:

            Énterprises -> Enterprises

        but:

            रेड -> रेड
            தமிழ் -> தமிழ்
            ಕನ್ನಡ -> ಕನ್ನಡ

        remain available.
        """

        if text is None:
            return ""

        text = str(text)

        # Unicode compatibility normalization
        text = unicodedata.normalize("NFKD", text)

        # Remove combining marks.
        text = "".join(
            char
            for char in text
            if unicodedata.category(char) != "Mn"
        )

        # Normalize whitespace.
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # ========================================================
    # TOKEN CLASSIFICATION
    # ========================================================

    def classify_number(self, value: str) -> TokenType:
        """
        Classify numeric tokens.

        Examples:

            833       -> HOUSE_NUMBER
            1056-1060 -> HOUSE_NUMBER
            560001    -> POSTAL_CODE

        Since the same numeric pattern can represent either a
        house number or postal code, the heuristic is conservative.
        """

        clean = value.replace(" ", "")

        # Range such as 1056-1060
        if re.fullmatch(r"\d+-\d+", clean):
            return TokenType.HOUSE_NUMBER

        # US ZIP
        if re.fullmatch(r"\d{5}(?:-\d{4})?", clean):
            return TokenType.POSTAL_CODE

        # Indian PIN
        if re.fullmatch(r"\d{6}", clean):
            return TokenType.POSTAL_CODE

        # General numeric value
        return TokenType.NUMBER

    # ========================================================
    # WORD CHECK
    # ========================================================

    @staticmethod
    def is_unicode_word(value: str) -> bool:
        """
        Returns True when value consists of Unicode letters.

        [^\\W\\d_] means:
            not non-word
            not digit
            not underscore

        Therefore it retains Unicode letters from scripts such
        as Latin, Devanagari, Tamil, Kannada, etc.
        """

        return bool(
            re.fullmatch(
                r"[^\W\d_]+",
                value,
                flags=re.UNICODE,
            )
        )

    # ========================================================
    # TOKENIZE
    # ========================================================

    def tokenize(self, text: str) -> List[Token]:
        """
        Main lexical-analysis function.

        It keeps:
            - Unicode words
            - numbers
            - house numbers
            - postal codes
            - legal suffixes
            - road types

        Punctuation is recognized separately when appropriate.
        """

        if not text:
            return []

        text = self.normalize_unicode(text)

        if not text:
            return []

        # ----------------------------------------------------
        # Unicode-safe tokenization
        # ----------------------------------------------------
        #
        # Group 1:
        #   numbers and ranges
        #
        # Group 2:
        #   Unicode letters
        #
        # Group 3:
        #   punctuation
        #
        pattern = (
            r"\d+(?:[-/]\d+)*"
            r"|[^\W\d_]+"
            r"|[^\w\s]"
        )

        raw_tokens = re.findall(
            pattern,
            text,
            flags=re.UNICODE,
        )

        tokens: List[Token] = []

        for raw in raw_tokens:

            if not raw:
                continue

            token = raw.strip()

            if not token:
                continue

            token_lower = token.casefold()

            # ------------------------------------------------
            # NUMBER
            # ------------------------------------------------

            if re.fullmatch(
                r"\d+(?:[-/]\d+)*",
                token,
            ):
                token_type = self.classify_number(token)

            # ------------------------------------------------
            # LEGAL SUFFIX
            # ------------------------------------------------

            elif token_lower in self.legal_suffixes:
                token_type = TokenType.LEGAL_SUFFIX

            # ------------------------------------------------
            # ROAD TYPE
            # ------------------------------------------------

            elif token_lower in self.road_types:
                token_type = TokenType.ROAD_TYPE

            # ------------------------------------------------
            # ADDRESS ABBREVIATION
            # ------------------------------------------------

            elif token_lower in self.address_abbreviations:
                token_type = TokenType.OTHER

            # ------------------------------------------------
            # UNICODE WORD
            # ------------------------------------------------

            elif self.is_unicode_word(token):
                token_type = TokenType.WORD

            # ------------------------------------------------
            # PUNCTUATION
            # ------------------------------------------------

            elif re.fullmatch(
                r"[^\w\s]",
                token,
                flags=re.UNICODE,
            ):
                token_type = TokenType.PUNCTUATION

            # ------------------------------------------------
            # OTHER
            # ------------------------------------------------

            else:
                token_type = TokenType.OTHER

            tokens.append(
                Token(
                    value=token,
                    token_type=token_type,
                )
            )

        return tokens

    # ========================================================
    # LEX
    # ========================================================

    def lex(self, text: str) -> List[Token]:
        """
        Alias for tokenize().

        This makes the class usable as a conventional compiler
        lexer:

            lexer.lex(text)
        """

        return self.tokenize(text)

    # ========================================================
    # LEX BUSINESS NAME
    # ========================================================

    def lex_business_name(self, business_name: str) -> List[Token]:
        """
        Lex only the business name.
        """

        return self.tokenize(business_name)

    # ========================================================
    # LEX ADDRESS
    # ========================================================

    def lex_address(self, address: str) -> List[Token]:
        """
        Lex only the business address.
        """

        return self.tokenize(address)

    # ========================================================
    # DEBUG / DISPLAY
    # ========================================================

    def print_tokens(self, text: str) -> None:
        """
        Print lexical analysis in a compiler-style format.
        """

        print("\nINPUT:")
        print(text)

        print("\nTOKENS:")
        print("-" * 70)

        tokens = self.tokenize(text)

        for index, token in enumerate(tokens):
            print(
                f"{index:3d} | "
                f"{token.value:<30} | "
                f"{token.token_type.value}"
            )

        print("-" * 70)
        print(f"Total tokens: {len(tokens)}")


# ============================================================
# TESTS
# ============================================================

def run_tests():

    lexer = Lexer()

    test_cases = [

        # ----------------------------------------------
        # English business name
        # ----------------------------------------------
        "Callicoat & Dailey Inc",

        # ----------------------------------------------
        # Indian address
        # ----------------------------------------------
        "797, Lake Town Block A, Kolkata, Howrah, West Bengal",

        # ----------------------------------------------
        # Address abbreviations
        # ----------------------------------------------
        "1056-1060 BELDEN AVE, PO BOX 8807, AKRON, OH",

        # ----------------------------------------------
        # Accented Latin
        # ----------------------------------------------
        "Payne Énterprises",

        # ----------------------------------------------
        # Hindi
        # ----------------------------------------------
        "रेड वेंचर्स प्राइवेट लिमिटेड",

        # ----------------------------------------------
        # Hindi + English
        # ----------------------------------------------
        "Raj Consulting Pvt Ltd, दिल्ली",

        # ----------------------------------------------
        # Tamil
        # ----------------------------------------------
        "ராஜ் இன்வெஸ்ட்மெண்ட்ஸ் LLP",

        # ----------------------------------------------
        # Kannada
        # ----------------------------------------------
        "ಲಕ್ಷ್ಮಿ ಗೋಲ್ಡನ್ ಇನ್ವೆಸ್ಟ್ಮೆಂಟ್ಸ್",

        # ----------------------------------------------
        # Mixed address
        # ----------------------------------------------
        "H.No. A-5 Gali No 20 G/F Madhu Vihar, Delhi",

        # ----------------------------------------------
        # US address
        # ----------------------------------------------
        "833 Reliance Street, Charlotte, NC 28202",
    ]

    print("=" * 80)
    print("UNICODE-SAFE CD LEXER TEST")
    print("=" * 80)

    for text in test_cases:

        print("\n")
        print("=" * 80)

        lexer.print_tokens(text)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_tests()