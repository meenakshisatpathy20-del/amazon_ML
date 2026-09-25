import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from lexer import tokenize, TokenType
from symbol_table import SymbolTable


# ============================================================
# STRUCTURED INTERMEDIATE REPRESENTATION
# ============================================================
#
# This is our Compiler Design IR.
#
# Raw record
#     ↓
# Lexer
#     ↓
# Symbol Table
#     ↓
# Parser
#     ↓
# EntityIR
#
# The IR will later feed:
#     - blocking
#     - pair features
#     - matcher
# ============================================================


@dataclass
class EntityIR:

    entity_id: str = ""

    original_name: str = ""
    original_address: str = ""
    country: str = ""

    # -----------------------------
    # Business-name representation
    # -----------------------------
    normalized_name: str = ""
    name_tokens: List[str] = field(default_factory=list)
    legal_suffix: Optional[str] = None

    # -----------------------------
    # Address representation
    # -----------------------------
    house_number: Optional[str] = None
    road_name: List[str] = field(default_factory=list)
    road_type: Optional[str] = None

    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None

    # -----------------------------
    # Useful matching representation
    # -----------------------------
    normalized_address: str = ""

    # All canonical tokens
    all_tokens: List[str] = field(default_factory=list)


# ============================================================
# PARSER
# ============================================================

class EntityParser:

    def __init__(self):

        self.symbol_table = SymbolTable()

    # ========================================================
    # BASIC CLEANING
    # ========================================================

    @staticmethod
    def clean_text(text):

        if text is None:
            return ""

        text = str(text).strip()

        text = re.sub(r"\s+", " ", text)

        return text


    # ========================================================
    # CANONICAL TOKENS
    # ========================================================

    def canonical_tokens(self, text):

        tokens = tokenize(text)

        result = []

        for token in tokens:

            # Ignore punctuation in the structured representation
            if token.token_type == TokenType.OTHER:
                continue

            canonical = self.symbol_table.canonicalize(
                token.normalized
            )

            result.append(
                (token, canonical)
            )

        return result


    # ========================================================
    # BUSINESS NAME PARSER
    # ========================================================

    def parse_name(self, name):

        name = self.clean_text(name)

        token_data = self.canonical_tokens(name)

        name_tokens = []
        legal_suffix = None

        for token, canonical in token_data:

            if token.token_type == TokenType.LEGAL_SUFFIX:

                legal_suffix = canonical

            else:

                name_tokens.append(canonical)

        normalized_name = " ".join(name_tokens)

        return (
            normalized_name,
            name_tokens,
            legal_suffix
        )


    # ========================================================
    # POSTAL CODE
    # ========================================================

    @staticmethod
    def extract_postal_code(address):

        if not address:
            return None

        # US ZIP / ZIP+4
        match = re.search(
            r"\b\d{5}(?:-\d{4})?\b",
            address
        )

        if match:
            return match.group(0)

        # Generic 6-digit postal / PIN
        match = re.search(
            r"\b\d{6}\b",
            address
        )

        if match:
            return match.group(0)

        # Generic alphanumeric postal code
        match = re.search(
            r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b",
            address.upper()
        )

        if match:
            return match.group(0).replace(" ", "")

        return None


    # ========================================================
    # HOUSE NUMBER
    # ========================================================

    @staticmethod
    def extract_house_number(address):

        if not address:
            return None

        # Examples:
        # 797
        # 797A
        # 12-14
        # H.No. 12
        # No. 45

        patterns = [

            r"^\s*(?:H\.?\s*No\.?|House\s*No\.?|No\.?)\s*([0-9]+[A-Za-z]?(?:[-/][0-9A-Za-z]+)?)",

            r"^\s*([0-9]+[A-Za-z]?(?:[-/][0-9A-Za-z]+)?)",

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                address,
                flags=re.IGNORECASE
            )

            if match:
                return match.group(1)

        return None


    # ========================================================
    # ROAD TYPE + ROAD NAME
    # ========================================================

    def parse_road(self, address):

        token_data = self.canonical_tokens(address)

        road_type = None
        road_name = []

        # Find first road type.
        # Tokens before it are possible road-name tokens.
        for index, (token, canonical) in enumerate(token_data):

            if token.token_type == TokenType.ROAD_TYPE:

                road_type = canonical

                # Look backwards for preceding words.
                for previous_token, previous_canonical in token_data[
                    max(0, index - 4):index
                ]:

                    if previous_token.token_type == TokenType.WORD:

                        road_name.append(previous_canonical)

                break

        return road_name, road_type


    # ========================================================
    # CITY / REGION HEURISTIC
    # ========================================================
    #
    # We deliberately keep this conservative.
    #
    # We don't want to hard-code a list of cities.
    # Later blocking/features can use the original token
    # representation as additional evidence.
    # ========================================================

    @staticmethod
    def parse_location(address, country):

        if not address:
            return None, None

        parts = [
            p.strip()
            for p in address.split(",")
            if p.strip()
        ]

        if len(parts) < 2:
            return None, None

        # Last part is often region/state.
        region = parts[-1]

        # Second-last is often city.
        city = parts[-2]

        # Avoid returning obvious numeric fragments as cities.
        if re.fullmatch(r"[\d\-/]+", city):
            city = None

        return city, region


    # ========================================================
    # NORMALIZED ADDRESS
    # ========================================================

    def normalize_address(self, address):

        token_data = self.canonical_tokens(address)

        normalized = []

        for token, canonical in token_data:

            normalized.append(canonical)

        return " ".join(normalized)


    # ========================================================
    # COMPLETE RECORD PARSER
    # ========================================================

    def parse_record(
        self,
        entity_id,
        business_name,
        business_address,
        country
    ):

        business_name = self.clean_text(business_name)
        business_address = self.clean_text(business_address)
        country = self.clean_text(country)

        # -----------------------------
        # Parse name
        # -----------------------------

        normalized_name, name_tokens, legal_suffix = (
            self.parse_name(business_name)
        )

        # -----------------------------
        # Parse address
        # -----------------------------

        house_number = self.extract_house_number(
            business_address
        )

        postal_code = self.extract_postal_code(
            business_address
        )

        road_name, road_type = self.parse_road(
            business_address
        )

        city, region = self.parse_location(
            business_address,
            country
        )

        normalized_address = self.normalize_address(
            business_address
        )

        # -----------------------------
        # All tokens
        # -----------------------------

        all_tokens = (
            name_tokens
            + road_name
        )

        return EntityIR(

            entity_id=entity_id,

            original_name=business_name,

            original_address=business_address,

            country=country,

            normalized_name=normalized_name,

            name_tokens=name_tokens,

            legal_suffix=legal_suffix,

            house_number=house_number,

            road_name=road_name,

            road_type=road_type,

            city=city,

            region=region,

            postal_code=postal_code,

            normalized_address=normalized_address,

            all_tokens=all_tokens
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    parser = EntityParser()

    examples = [

        {
            "id": "S1-TEST-1",
            "name": "Callicoat & Dailey Inc",
            "address": "833 Reliance Street, Charlotte, NC",
            "country": "US"
        },

        {
            "id": "S1-TEST-2",
            "name": "Lumay Boral",
            "address": "1056 Belden Avenue, Akron, OH",
            "country": "US"
        },

        {
            "id": "S1-TEST-3",
            "name": "Raj Consulting Pvt Ltd",
            "address": "701, Dlf Tower A, Jasola New Delhi, Delhi, New Delhi, Delhi",
            "country": "India"
        },

        {
            "id": "S1-TEST-4",
            "name": "Red Ventures Private Limited",
            "address": "Rajasthan, Jaipur, Banipark, Gokul Apartment, E-3A Kanti Chandra Road, G-1",
            "country": "India"
        },
    ]

    print("=" * 80)
    print("COMPILER DESIGN PARSER / STRUCTURED IR TEST")
    print("=" * 80)

    for example in examples:

        entity = parser.parse_record(
            example["id"],
            example["name"],
            example["address"],
            example["country"]
        )

        print("\n" + "-" * 80)

        print("ENTITY ID       :", entity.entity_id)
        print("ORIGINAL NAME   :", entity.original_name)
        print("NORMALIZED NAME :", entity.normalized_name)
        print("NAME TOKENS     :", entity.name_tokens)
        print("LEGAL SUFFIX    :", entity.legal_suffix)

        print("HOUSE NUMBER    :", entity.house_number)
        print("ROAD NAME       :", entity.road_name)
        print("ROAD TYPE       :", entity.road_type)

        print("CITY            :", entity.city)
        print("REGION          :", entity.region)
        print("POSTAL CODE     :", entity.postal_code)

        print("NORMALIZED ADDR :", entity.normalized_address)

        print("ALL TOKENS      :", entity.all_tokens)

    print("\n" + "=" * 80)
    print("PARSER TEST COMPLETE")
    print("=" * 80)