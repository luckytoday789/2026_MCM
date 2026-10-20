"""One all-supplied-row prior from explicit generated CSV bytes, without I/O.

This generated-only component authenticates no competition input and authorizes
no production run. Production loaders and source acceptance are separate gates.
The existing four-fold calibration entry points retain their original guards.
"""

import csv
from dataclasses import dataclass
import io
import math

from .policy_calibration import (
    CalibrationRow, FIELDS, SERIALIZATION, canonical_bytes, digest,
)
from .policy_pilot import EmpiricalPrior, real_gross


@dataclass(frozen=True)
class GeneratedRefit:
    input_sha256: str
    input_bytes: int
    scenario_count: int
    periods: int
    training_keys: tuple
    training_rows_sha256: str
    real_gross_sha256: str
    prior: EmpiricalPrior

    def manifest(self):
        """Return detached provenance; no fold/evaluation claims are invented."""
        count = len(self.training_keys)
        return {
            "schema_version": 1,
            "calibration_kind": "all_development_refit",
            "split": "synthetic",
            "input_origin": "program_generated",
            "source_verified": False,
            "production_execution_authorized": False,
            "input_sha256": self.input_sha256,
            "input_bytes": self.input_bytes,
            "scenario_count": self.scenario_count,
            "periods": self.periods,
            "training_scenario_ids": list(range(1, self.scenario_count + 1)),
            "training_row_keys": [list(key) for key in self.training_keys],
            "training_row_count": count,
            "training_rows_sha256": self.training_rows_sha256,
            "real_gross_sha256": self.real_gross_sha256,
            "annual_weight": "1 / training_row_count",
            "annual_weight_value": 1.0 / count,
            "asset_order": list(FIELDS[2:5]),
            "canonical_serialization": SERIALIZATION,
            "evaluation_partition_status": "not_applicable",
            "evaluation_scenario_ids": None,
            "fold_id": None,
        }


def build_generated_refit(data, *, scenario_count, periods):
    """Use every complete ordered supplied annual row exactly once, equally.

    No default path or file access exists. The 120-by-30 generated shape tests
    the production-sized arithmetic but does not identify original data bytes.
    """
    if type(data) is not bytes:
        raise ValueError("supply exact generated CSV bytes")
    if (type(scenario_count) is not int or not 1 <= scenario_count <= 120
            or type(periods) is not int or not 1 <= periods <= 30):
        raise ValueError("generated shape requires 1..120 scenarios and 1..30 periods")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("exact ordered six-field schema required")
        records = tuple(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("valid UTF-8 generated CSV required") from exc
    if len(records) != scenario_count * periods:
        raise ValueError("complete supplied shape required")
    rows = []
    for index, row in enumerate(records):
        scenario, period = divmod(index, periods)
        if (tuple(row) != FIELDS or row["scenario_id"] != str(scenario + 1)
                or row["period"] != str(period + 1)):
            raise ValueError("complete unique ordered canonical integer keys required")
        try:
            values = tuple(float(row[name]) for name in FIELDS[2:])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("finite numeric outcomes required") from exc
        if any(not math.isfinite(v) or v <= -1 for v in values):
            raise ValueError("strictly positive finite nominal/CPI gross factors required")
        real_gross(values[:3], values[3])
        rows.append(CalibrationRow(scenario + 1, period + 1, values[:3], values[3]))
    keys = tuple((row.scenario_id, row.period) for row in rows)
    gross = tuple(real_gross(row.returns, row.inflation) for row in rows)
    nominal_payload = {"schema": "training-annual-simple-v1", "fields": list(FIELDS),
                       "rows": [row.canonical_record() for row in rows]}
    gross_payload = {"schema": "training-real-gross-v1", "asset_order": list(FIELDS[2:5]),
                     "rows": [[*key, *(v.hex() for v in g)]
                              for key, g in zip(keys, gross)]}
    return GeneratedRefit(
        digest(data), len(data), scenario_count, periods, keys,
        digest(canonical_bytes(nominal_payload)),
        digest(canonical_bytes(gross_payload)), EmpiricalPrior(gross),
    )
