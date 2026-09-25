import sys
from pathlib import Path

# Allow imports from src/
SRC_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexer import tokenize, TokenType
from symbol_table import SymbolTable
from parser import EntityParser


# ============================================================
# COMPILER-DESIGN ENTITY PIPELINE
# ============================================================
#
# RAW ENTITY
#     ↓
# LEXER
#     ↓
# TOKEN CLASSIFICATION
#     ↓
# SYMBOL TABLE
#     ↓
# PARSER
#     ↓
# STRUCTURED ENTITY IR
#     ↓
# MODEL FEATURES
#
# This class is the single entry point that we will later use
# for ALL train/test records.
# ============================================================


class CDEntityPipeline:

    def __init__(self):

        self.symbol_table = SymbolTable()

        self.parser = EntityParser()


    # ========================================================
    # PROCESS ONE ENTITY
    # ========================================================

    def process(
        self,
        entity_id,
        business_name,
        business_address,
        country
    ):

        # ----------------------------------------------------
        # PHASE 1: LEXER
        # ----------------------------------------------------

        name_tokens = tokenize(
            business_name or ""
        )

        address_tokens = tokenize(
            business_address or ""
        )


        # ----------------------------------------------------
        # PHASE 2: SYMBOL TABLE
        # ----------------------------------------------------

        name_canonical_tokens = []

        for token in name_tokens:

            # Ignore punctuation
            if token.token_type == TokenType.OTHER:
                continue

            canonical = self.symbol_table.canonicalize(
                token.normalized
            )

            name_canonical_tokens.append(
                canonical
            )


        address_canonical_tokens = []

        for token in address_tokens:

            if token.token_type == TokenType.OTHER:
                continue

            canonical = self.symbol_table.canonicalize(
                token.normalized
            )

            address_canonical_tokens.append(
                canonical
            )


        # ----------------------------------------------------
        # PHASE 3: PARSER
        # ----------------------------------------------------

        ir = self.parser.parse_record(
            entity_id=entity_id,
            business_name=business_name,
            business_address=business_address,
            country=country
        )


        # ----------------------------------------------------
        # PHASE 4: ADD CD-DERIVED INFORMATION
        # ----------------------------------------------------

        return {
            "entity_id": ir.entity_id,

            # Original information
            "original_name": ir.original_name,
            "original_address": ir.original_address,
            "country": ir.country,

            # -------------------------
            # Lexer output
            # -------------------------

            "name_lexeme_count": len(name_tokens),
            "address_lexeme_count": len(address_tokens),

            "name_token_types": [
                token.token_type.value
                for token in name_tokens
            ],

            "address_token_types": [
                token.token_type.value
                for token in address_tokens
            ],

            # -------------------------
            # Symbol-table output
            # -------------------------

            "canonical_name_tokens": name_canonical_tokens,

            "canonical_address_tokens":
                address_canonical_tokens,

            # -------------------------
            # Parser / IR output
            # -------------------------

            "normalized_name":
                ir.normalized_name,

            "name_tokens":
                ir.name_tokens,

            "legal_suffix":
                ir.legal_suffix,

            "house_number":
                ir.house_number,

            "road_name":
                ir.road_name,

            "road_type":
                ir.road_type,

            "city":
                ir.city,

            "region":
                ir.region,

            "postal_code":
                ir.postal_code,

            "normalized_address":
                ir.normalized_address,

            "all_tokens":
                ir.all_tokens,
        }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    pipeline = CDEntityPipeline()


    examples = [

        (
            "S1-TEST-1",
            "Hendricks and Flowers Inc",
            "33 Sleepy Hollow Drive, Danbury, CT",
            "US"
        ),

        (
            "S1-TEST-2",
            "Lumay Boral",
            "1056 Belden Avenue, Akron, OH",
            "US"
        ),

        (
            "S1-TEST-3",
            "Raj Consulting Pvt Ltd",
            "701, Dlf Tower A, Jasola New Delhi, Delhi, New Delhi, Delhi",
            "India"
        ),

        (
            "S1-TEST-4",
            "Red Ventures Private Limited",
            "Rajasthan, Jaipur, Banipark, Gokul Apartment, E-3A Kanti Chandra Road, G-1",
            "India"
        ),

        (
            "S1-TEST-5",
            "Payne Énterprises",
            "3315 FREMONT ST, PEORIA, IL",
            "US"
        ),
    ]


    print("=" * 80)
    print("COMPILER DESIGN ENTITY PIPELINE")
    print("=" * 80)


    for entity_id, name, address, country in examples:

        result = pipeline.process(
            entity_id,
            name,
            address,
            country
        )


        print("\n" + "-" * 80)

        print("ENTITY ID:")
        print(result["entity_id"])

        print("\nORIGINAL NAME:")
        print(result["original_name"])

        print("\nCANONICAL NAME TOKENS:")
        print(result["canonical_name_tokens"])

        print("\nNORMALIZED NAME:")
        print(result["normalized_name"])

        print("\nLEGAL SUFFIX:")
        print(result["legal_suffix"])

        print("\nHOUSE NUMBER:")
        print(result["house_number"])

        print("\nROAD NAME:")
        print(result["road_name"])

        print("\nROAD TYPE:")
        print(result["road_type"])

        print("\nCITY:")
        print(result["city"])

        print("\nREGION:")
        print(result["region"])

        print("\nPOSTAL CODE:")
        print(result["postal_code"])

        print("\nCANONICAL ADDRESS TOKENS:")
        print(result["canonical_address_tokens"])

        print("\nNORMALIZED ADDRESS:")
        print(result["normalized_address"])


    print("\n" + "=" * 80)
    print("CD PIPELINE TEST COMPLETE")
    print("=" * 80)