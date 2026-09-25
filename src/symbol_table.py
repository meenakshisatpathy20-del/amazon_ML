from lexer import TokenType


# ============================================================
# COMPILER DESIGN SYMBOL TABLE
# ============================================================
#
# Maps different surface forms to one canonical representation.
#
# Example:
#   INC
#   INC.
#   INCORPORATED
#       ↓
#   INCORPORATED
#
#   RD
#   RD.
#   ROAD
#       ↓
#   ROAD
#
# ============================================================


class SymbolTable:

    def __init__(self):

        # ----------------------------------------------------
        # Legal entity suffixes
        # ----------------------------------------------------
        self.legal_suffixes = {

            "inc": "incorporated",
            "inc.": "incorporated",
            "incorporated": "incorporated",

            "llc": "limited_liability_company",
            "l.l.c": "limited_liability_company",

            "ltd": "limited",
            "ltd.": "limited",
            "limited": "limited",

            "pvt": "private",
            "pvt.": "private",
            "private": "private",

            "plc": "public_limited_company",

            "llp": "limited_liability_partnership",

            "corp": "corporation",
            "corp.": "corporation",
            "corporation": "corporation",

            "co": "company",
            "co.": "company",
            "company": "company",
        }


        # ----------------------------------------------------
        # Road / address abbreviations
        # ----------------------------------------------------
        self.road_types = {

            "rd": "road",
            "rd.": "road",
            "road": "road",

            "st": "street",
            "st.": "street",
            "street": "street",

            "ave": "avenue",
            "ave.": "avenue",
            "avenue": "avenue",

            "blvd": "boulevard",
            "blvd.": "boulevard",
            "boulevard": "boulevard",

            "dr": "drive",
            "dr.": "drive",
            "drive": "drive",

            "ln": "lane",
            "ln.": "lane",
            "lane": "lane",

            "hwy": "highway",
            "hwy.": "highway",
            "highway": "highway",

            "pkwy": "parkway",
            "pkwy.": "parkway",
            "parkway": "parkway",

            "cir": "circle",
            "cir.": "circle",
            "circle": "circle",

            "ct": "court",
            "ct.": "court",
            "court": "court",

            "ter": "terrace",
            "ter.": "terrace",
            "terrace": "terrace",

            "pl": "place",
            "pl.": "place",
            "place": "place",
        }


        # ----------------------------------------------------
        # Common address abbreviations
        # ----------------------------------------------------
        self.address_terms = {

            "apt": "apartment",
            "apt.": "apartment",

            "fl": "floor",
            "fl.": "floor",

            "ste": "suite",
            "ste.": "suite",

            "hno": "house_number",
            "h.no": "house_number",

            "no": "number",
            "no.": "number",

            "po": "post_office",
            "p.o": "post_office",

            "pobox": "post_box",
            "po.box": "post_box",

            "blk": "block",
            "blk.": "block",

            "bldg": "building",
            "bldg.": "building",
        }


    # ========================================================
    # LOOKUP
    # ========================================================

    def lookup(self, token):

        token = token.lower().strip()

        if token in self.legal_suffixes:
            return self.legal_suffixes[token]

        if token in self.road_types:
            return self.road_types[token]

        if token in self.address_terms:
            return self.address_terms[token]

        return token


    # ========================================================
    # CANONICALIZE TOKEN
    # ========================================================

    def canonicalize(self, token):

        return self.lookup(token)


    # ========================================================
    # CLASSIFICATION + CANONICALIZATION
    # ========================================================

    def transform(self, token):

        canonical = self.canonicalize(token.normalized)

        return {
            "original": token.text,
            "normalized": token.normalized,
            "canonical": canonical,
            "type": token.token_type.value,
            "position": token.position
        }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    table = SymbolTable()

    examples = [
        "Inc",
        "INC.",
        "Incorporated",
        "Ltd",
        "LTD.",
        "Private",
        "Pvt",
        "PVT.",
        "Road",
        "Rd",
        "RD.",
        "Avenue",
        "Ave",
        "Apartment",
        "Apt",
        "Block",
        "Blk",
    ]

    print("=" * 70)
    print("SYMBOL TABLE TEST")
    print("=" * 70)

    for value in examples:

        print(
            f"{value:<18} -> "
            f"{table.canonicalize(value)}"
        )