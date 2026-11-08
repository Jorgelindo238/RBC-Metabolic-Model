"""Conservative, compartment-preserving comparison with pinned RBC-GEM JSON."""

import math
import re


# Ambiguous/generic ODE pools (METTHF, METCYT, AA, GLUAA) stay unmapped.
POOL_IDS = {
    "GLC": "glc__D", "G6P": "g6p", "F6P": "f6p", "GL6P": "6pgl", "GO6P": "6pgc",
    "RU5P": "ru5p__D", "R5P": "r5p", "X5P": "xu5p__D", "E4P": "e4p", "S7P": "s7p",
    "GA3P": "g3p", "F16BP": "fdp", "DHCP": "dhap", "B13PG": "13dpg", "P3G": "3pg",
    "B23PG": "23dpg", "P2G": "2pg", "PEP": "pep", "PYR": "pyr", "LAC": "lac__L",
    "MAL": "mal__L", "OAA": "oaa", "CIT": "cit", "COA": "coa", "SUCCOA": "succoa",
    "ADE": "ade", "ADO": "adn", "INO": "ins", "HYPX": "hxan", "XAN": "xan", "URT": "urate",
    "GUA": "gua", "R1P": "r1p", "D2RIBP": "2dr1p", "DEOXYINO": "2dins",
    "ATP": "atp", "ADP": "adp", "AMP": "amp", "GTP": "gtp", "GDP": "gdp", "GMP": "gmp",
    "PRPP": "prpp", "IMP": "imp", "XMP": "xmp", "ADESUC": "succamp",
    "CYSTHIO": "cyst__L", "HCYS": "hcys__L", "MET": "met__L", "THF": "thf",
    "ADOMET": "amet__L", "SAH": "ahcys__L", "ARG": "arg__L", "ARGSUC": "argsuc",
    "CITR": "citr__L", "ASP": "asp__L", "SER": "ser__L", "ALA": "ala__L", "AKG": "akg",
    "GLU": "glu__L", "GLN": "gln__L", "NH4": "nh4", "OXOP": "5oxpro", "GLY": "gly",
    "CYS": "cys__L", "CYSGLY": "cysgly", "GLUCYS": "gglucys__L", "GSH": "gthrd", "GSSG": "gthox",
    "ORN": "orn__L", "UREA": "urea", "ACCOA": "accoa", "NAD": "nad", "NADH": "nadh",
    "NADP": "nadp", "NADPH": "nadph", "H2O2": "h2o2", "O2": "o2", "FUM": "fum",
    "RIB": "rib__D", "CYT": "cytd", "ASN": "asn__L",
}
EXTERNAL_POOLS = {
    "EGLC": "GLC", "ENH4": "NH4", "ELAC": "LAC", "EADO": "ADO", "EADE": "ADE",
    "EINO": "INO", "EGLN": "GLN", "EGLU": "GLU", "ECYS": "CYS", "EMET": "MET",
    "EASP": "ASP", "EUREA": "UREA", "EURT": "URT", "EPYR": "PYR", "EXAN": "XAN",
    "EHYPX": "HYPX", "EMAL": "MAL", "EFUM": "FUM", "ECIT": "CIT", "EALA": "ALA",
    "ECYT": "CYT", "EOXOP": "OXOP", "ESER": "SER", "EARG": "ARG", "EGSSG": "GSSG",
    "EGSH": "GSH", "EASN": "ASN",
}
CURRENCY_IDS = frozenset(f"{base}_{compartment}" for base in ("h", "h2o", "pi", "ppi", "co2")
                         for compartment in ("c", "e"))


def pool_mapping(model):
    available = {row["id"] for row in model["metabolites"]}
    proposed = {name: value + "_c" for name, value in POOL_IDS.items()}
    proposed.update({name: POOL_IDS[parent] + "_e" for name, parent in EXTERNAL_POOLS.items()})
    return {name: value for name, value in proposed.items() if value in available}


def signature(stoichiometry):
    """Normalize only scale; preserve every species and sign."""
    values = {name: float(value) for name, value in stoichiometry.items() if value != 0}
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("nonfinite stoichiometry")
    if not values:
        return ()
    scale = min(abs(value) for value in values.values())
    return tuple(sorted((name, round(value / scale, 12)) for name, value in values.items()))


def reverse_signature(stoichiometry):
    return signature({name: -value for name, value in stoichiometry.items()})


def project_gem(reaction, inverse_mapping):
    result, unmodeled, currency = {}, {}, {}
    for name, coefficient in reaction["metabolites"].items():
        if name in inverse_mapping:
            result[inverse_mapping[name]] = coefficient
        elif name in CURRENCY_IDS:
            currency[name] = coefficient
        else:
            unmodeled[name] = coefficient
    return result, unmodeled, currency


def compare_network(model, ode_stoichiometry):
    mapping = pool_mapping(model)
    inverse = {value: name for name, value in mapping.items()}
    if len(inverse) != len(mapping):
        raise ValueError("pool mapping must not merge distinct ODE pools")
    index = {}
    projected = []
    for reaction in model["reactions"]:
        stoich, missing, currency = project_gem(reaction, inverse)
        row = {"gem_id": reaction["id"], "name": reaction["name"], "gpr": reaction["gene_reaction_rule"],
               "lower_bound": reaction["lower_bound"], "upper_bound": reaction["upper_bound"],
               "subsystem": reaction.get("subsystem", ""), "projected": stoich,
               "unmodeled": missing, "omitted_currency": currency,
               "references": reaction.get("annotation", {}).get("references", []),
               "full_stoichiometry": reaction["metabolites"]}
        projected.append(row)
        if stoich and not missing:
            index.setdefault(signature(stoich), []).append(row)
    comparisons, covered = [], set()
    for name, stoich in sorted(ode_stoichiometry.items()):
        unknown = sorted(set(stoich).difference(mapping))
        forward = index.get(signature(stoich), []) if not unknown else []
        reverse = index.get(reverse_signature(stoich), []) if not unknown else []
        for match in forward + reverse:
            covered.add(match["gem_id"])
        comparisons.append({"ode_reaction": name, "ode_stoichiometry": stoich,
                            "unmapped_ode_pools": unknown,
                            "forward_matches": [row["gem_id"] for row in forward],
                            "reverse_matches": [row["gem_id"] for row in reverse],
                            "status": "pool_identity_unresolved" if unknown else (
                                "projected_equivalent" if forward or reverse else "no_single_reaction_match")})
    closed = [row for row in projected if row["projected"] and not row["unmodeled"]
              and row["gem_id"] not in covered
              and not row["gem_id"].startswith(("EX_", "SK_", "DM_"))]
    return {"pool_mapping": mapping, "comparisons": comparisons,
            "closed_unmatched_candidates": closed, "projected_inventory": projected}


def parse_catalog(text):
    """Read the local format strictly without adding undeclared species."""
    sections, section, reactions = {}, None, {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            section = line[1:]
            sections.setdefault(section, [])
        elif section == "CAT":
            name, equation = line.split(":", 1)
            name = name.strip()
            if name in reactions:
                raise ValueError("duplicate reaction")
            sides = re.split(r"=>|=", equation)
            if len(sides) != 2:
                raise ValueError("invalid reaction equation")
            stoich = {}
            for side, sign in zip(sides, (-1, 1)):
                for term in side.split("+"):
                    term = term.strip()
                    if not term:
                        continue
                    match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s+)?([A-Za-z][A-Za-z0-9_]*)", term)
                    if match is None:
                        raise ValueError(f"invalid species term: {term}")
                    coefficient, species = match.groups()
                    stoich[species] = stoich.get(species, 0.0) + sign * float(coefficient or 1)
            reactions[name] = {key: value for key, value in stoich.items() if value}
        elif section:
            sections[section].extend(line.split())
        else:
            raise ValueError("content outside a section")
    return sections, reactions


def catalog_differences(reactions, ode_stoichiometry):
    differences = []
    for name in sorted(set(reactions) | set(ode_stoichiometry)):
        old, new = reactions.get(name), ode_stoichiometry.get(name)
        if old != new:
            differences.append({"reaction": name, "catalog": old, "ode": new,
                                "status": "missing_catalog" if old is None else (
                                    "absent_ode" if new is None else "coefficient_or_orientation_mismatch")})
    return differences
