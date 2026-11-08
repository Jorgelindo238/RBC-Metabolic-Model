"""Source-preserving JBC import; no conversion to model states or flux teachers."""

from __future__ import annotations

import math
from collections import Counter

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


SCHEDULES = {
    4: [0, 1.0417, 3, 7.0417, 10, 14.0417, 17, 20.9583],
    13: [0, .3083, 1, 2.3333, 3.3333, 4.3333, 5.9167, 7.0417, 10, 14.0417, 20.9583],
    22: [0, .1875, .3708, 1, 1.375, 1.875, 2.875, 3.25, 3.9583, 7, 14, 20.9167],
    37: [0, .125, .3708, 1, 1.375, 1.875, 2.25, 2.875, 3.9167, 7],
}
SHEET_CHANNEL_COUNTS = {"endo": 47, "exo": 23, "assay": 26}
TEMPERATURE_LABELS = {f"{temperature} degrees C": temperature for temperature in SCHEDULES}
LABEL_TO_STATE = {
    "5-oxoproline": "OXOP", "6-phosphogluconate": "GO6P",
    "ADP": "ADP", "AMP": "AMP", "ATP": "ATP", "adenine": "ADE",
    "citrate": "CIT", "D-glucose": "GLC", "fructose-1,6-bisphosphate": "F16BP",
    "GMP": "GMP", "glucose-6-phosphate": "G6P", "oxidized glutathione": "GSSG",
    "reduced glutathione": "GSH", "hypoxanthine": "HYPX", "IMP": "IMP", "inosine": "INO",
    "L-arginine": "ARG", "L-asparagine": "ASN", "L-aspartate": "ASP",
    "L-glutamate": "GLU", "L-glutamine": "GLN", "L-lactate": "LAC",
    "L-serine": "SER", "malate": "MAL", "phosphoenolpyruvate": "PEP",
    "S-adenosylhomocysteine": "SAH", "xanthine": "XAN",
}


def schedule(sheet, temperature):
    return SCHEDULES[temperature] + ([14] if sheet == "assay" and temperature == 37 else [])


def channel_mapping(label, sheet, unit):
    exact = label.strip()
    compartment = "intracellular" if exact.endswith("(endo)") else "extracellular" if exact.endswith("(exo)") else "unspecified"
    base = exact.removesuffix(" (endo)").removesuffix(" (exo)")
    mapping = {"candidate_model_pools": "", "candidate_operator": "",
               "mapping_status": "unmapped", "compartment": compartment,
               "channel_kind": "metabolite_concentration" if sheet in ("endo", "exo") else "physiology_or_assay",
               "volume_basis_verified": False, "pool_definition_verified": False,
               "training_enabled": False}
    if unit != "mM":
        return mapping
    if base == "phosphoglycerate pool" and compartment == "intracellular":
        mapping.update(candidate_model_pools="P2G|P3G", candidate_operator="P2G + P3G",
                       mapping_status="candidate_pooled_sum_do_not_split")
    elif base in LABEL_TO_STATE and compartment != "unspecified":
        pool = LABEL_TO_STATE[base]
        pool = "E" + pool if compartment == "extracellular" else pool
        mapping.update(candidate_model_pools=pool, candidate_operator=pool,
                       mapping_status="candidate_identity_pending_observation_contract")
        if base == "ATP":
            mapping["mapping_status"] = "hold_ATP_compartment_and_free_total_ambiguity"
        elif base == "glucose-6-phosphate":
            mapping["mapping_status"] = "hold_hexose_6_phosphate_assay_identity"
    if mapping["candidate_model_pools"]:
        mapping["channel_kind"] = "metabolite_concentration"
    return mapping


def numeric_value(value, location):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"nonfinite, formula or nonnumeric source value: {location}")
    return value


def read_workbook(path):
    """Infer positional replicate blocks, never claim their donor identities."""
    workbook = load_workbook(path, read_only=True, data_only=False)
    channels, samples, observations = [], [], []
    try:
        if workbook.sheetnames != list(SHEET_CHANNEL_COUNTS):
            raise ValueError("expected endo/exo/assay sheets in the supplied supplement")
        for sheet in workbook:
            if sheet.max_column != SHEET_CHANNEL_COUNTS[sheet.title] + 2:
                raise ValueError(f"unexpected channel count: {sheet.title}")
            rows = list(sheet.iter_rows(values_only=True))
            if rows[0][1] != "time" or rows[1][1] != "days":
                raise ValueError("source time header/units changed")
            headers = Counter(str(value).strip() for value in rows[0][2:])
            sheet_channels = []
            for column, (label, unit) in enumerate(zip(rows[0][2:], rows[1][2:]), start=3):
                if not isinstance(label, str) or not isinstance(unit, str):
                    raise ValueError("explicit source headers and units required")
                letter = get_column_letter(column)
                entry = {"channel_id": f"{sheet.title}!{letter}", "sheet": sheet.title,
                         "excel_column": letter, "exact_source_label": label, "source_unit": unit,
                         "duplicate_label": headers[label.strip()] > 1,
                         **channel_mapping(label, sheet.title, unit)}
                channels.append(entry)
                sheet_channels.append(entry)
            temperature, replicate, previous = None, 0, None
            temperature_label, temperature_cell = None, None
            seen = set()
            group_times = {}
            for row_number, row in enumerate(rows[2:], start=3):
                if all(value is None for value in row):
                    continue
                if row[0] is not None:
                    temperature_label = row[0]
                    if not isinstance(temperature_label, str) or temperature_label not in TEMPERATURE_LABELS:
                        raise ValueError("unknown source temperature label")
                    temperature = TEMPERATURE_LABELS[temperature_label]
                    temperature_cell = f"A{row_number}"
                    if temperature in seen:
                        raise ValueError("unknown or repeated temperature block")
                    seen.add(temperature)
                    replicate, previous = 0, None
                if temperature is None:
                    raise ValueError("sample without temperature block")
                day = numeric_value(row[1], f"{sheet.title}!B{row_number}")
                if day is None or day < 0:
                    raise ValueError("nonnegative explicit source day required")
                if day == 0:
                    replicate += 1
                    previous = None
                if not 1 <= replicate <= 3 or previous is not None and day <= previous:
                    raise ValueError("invalid positional replicate/time sequence")
                previous = day
                group_times.setdefault((temperature, replicate), []).append(day)
                sample = {"sample_id": f"{sheet.title}!row{row_number}", "sheet": sheet.title,
                          "excel_row": row_number, "temperature_C": temperature,
                          "source_temperature_label": temperature_label, "temperature_source_cell": temperature_cell,
                          "replicate_block_index": replicate, "donor_id": "",
                          "cross_sheet_pairing_verified": False, "source_day": day,
                          "storage_day_from_documented_origin": day + 1,
                          "time_origin_evidence": "supplement PDF p2: first sample one day after storage began"}
                samples.append(sample)
                for channel, value in zip(sheet_channels, row[2:]):
                    location = f"{channel['excel_column']}{row_number}"
                    value = numeric_value(value, f"{sheet.title}!{location}")
                    if value is not None and value < 0 and channel["source_unit"] == "mM":
                        raise ValueError("negative concentration: " + location)
                    observations.append({**sample, "channel_id": channel["channel_id"],
                                         "source_cell": location, "exact_source_label": channel["exact_source_label"],
                                         "source_unit": channel["source_unit"], "value": value,
                                         "is_missing": value is None, "is_zero": value == 0,
                                         "source_volume_conversion_applied": False, "training_enabled": False})
            expected_groups = {(temp, rep) for temp in SCHEDULES for rep in (1, 2, 3)}
            if set(group_times) != expected_groups or any(times != schedule(sheet.title, temp)
                    for (temp, _), times in group_times.items()):
                raise ValueError("incomplete or altered source sampling schedule")
        return channels, samples, observations
    finally:
        workbook.close()
