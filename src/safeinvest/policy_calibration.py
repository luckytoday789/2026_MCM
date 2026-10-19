"""Provisional four-fold calibration with byte/row provenance; synthetic API only.

No filesystem access, CLI, final support, or strategy outcomes. Chief-authored
code requires independent Sol review before any production integration.
"""

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math

from .policy_pilot import EmpiricalPrior, real_gross

FIELDS = ("scenario_id", "period", "equity_return", "bond_return",
          "bill_proxy_return", "inflation")
FOLDS = 4
SERIALIZATION = "safeinvest-calibration-v1: compact ASCII JSON, sorted object keys, float.hex, no newline"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fold_id(scenario_id):
    if type(scenario_id) is not int or scenario_id < 1:
        raise ValueError("scenario_id must be a positive integer")
    return (scenario_id - 1) % FOLDS


@dataclass(frozen=True)
class CalibrationRow:
    scenario_id: int
    period: int
    returns: tuple
    inflation: float

    def canonical_record(self):
        return [self.scenario_id, self.period,
                *(v.hex() for v in (*self.returns, self.inflation))]


@dataclass(frozen=True)
class FoldCalibration:
    fold: int
    training_ids: tuple
    evaluation_ids: tuple
    training_keys: tuple
    training_rows_sha256: str
    real_gross_sha256: str
    prior: EmpiricalPrior

    def manifest(self):
        return {"fold_id": self.fold,
                "training_scenario_ids": list(self.training_ids),
                "evaluation_scenario_ids": list(self.evaluation_ids),
                "training_row_keys": [list(key) for key in self.training_keys],
                "training_row_count": len(self.training_keys),
                "training_rows_sha256": self.training_rows_sha256,
                "real_gross_sha256": self.real_gross_sha256,
                "annual_weight": "1 / training_row_count",
                "asset_order": list(FIELDS[2:5])}


@dataclass(frozen=True)
class CalibrationBundle:
    input_sha256: str
    input_bytes: int
    scenario_count: int
    periods: int
    folds: tuple

    def manifest(self):
        # Fresh containers prevent a caller from mutating the saved calibration.
        return {"schema_version": 1, "split": "synthetic",
                "production_execution_authorized": False,
                "input_sha256": self.input_sha256, "input_bytes": self.input_bytes,
                "scenario_count": self.scenario_count, "periods": self.periods,
                "fold_assignment": "(scenario_id - 1) % 4",
                "canonical_serialization": SERIALIZATION,
                "folds": [fold.manifest() for fold in self.folds]}


def _parse_synthetic(data, scenario_count, periods):
    if type(data) is not bytes:
        raise ValueError("supply exact fixture CSV bytes")
    if (type(scenario_count) is not int or scenario_count < FOLDS
            or scenario_count % FOLDS or type(periods) is not int or periods < 1):
        raise ValueError("synthetic fixture requires a positive multiple of four scenarios and positive periods")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError("exact ordered six-field schema required")
    records = tuple(reader)
    if len(records) != scenario_count * periods:
        raise ValueError("fixture row count mismatch")
    parsed = []
    for index, row in enumerate(records):
        scenario, period = divmod(index, periods)
        if (tuple(row) != FIELDS or row["scenario_id"] != str(scenario + 1)
                or row["period"] != str(period + 1)):
            raise ValueError("complete unique ordered scenario/period keys required")
        try:
            numbers = tuple(float(row[name]) for name in FIELDS[2:])
        except (TypeError, ValueError) as exc:
            raise ValueError("outcomes must be numeric") from exc
        if any(not math.isfinite(v) or v <= -1 for v in numbers):
            raise ValueError("finite strictly positive nominal/CPI gross factors required")
        # Validate positive finite real factors even for evaluation rows. This
        # diagnoses bad input; those values never enter that fold's fitted prior.
        real_gross(numbers[:3], numbers[3])
        parsed.append(CalibrationRow(scenario+1, period+1, numbers[:3], numbers[3]))
    return tuple(parsed)


def build_synthetic_calibrations(data, *, scenario_count, periods):
    """Fit four fixed OOF marginal distributions from explicit generated CSV bytes.

    This seam never opens a path or claims the bytes are original competition
    data. A future reviewed production loader must independently bind its fixed
    development path/hash and 120-by-30 shape before using any shared machinery.
    """
    rows = _parse_synthetic(data, scenario_count, periods)
    calibrations = []
    ids = tuple(range(1, scenario_count+1))
    for fold in range(FOLDS):
        train_ids = tuple(s for s in ids if fold_id(s) != fold)
        evaluation_ids = tuple(s for s in ids if fold_id(s) == fold)
        train = tuple(row for row in rows if fold_id(row.scenario_id) != fold)
        keys = tuple((row.scenario_id, row.period) for row in train)
        gross = tuple(real_gross(row.returns, row.inflation) for row in train)
        row_payload = {"schema": "training-annual-simple-v1", "fields": list(FIELDS),
                       "rows": [row.canonical_record() for row in train]}
        gross_payload = {"schema": "training-real-gross-v1", "asset_order": list(FIELDS[2:5]),
                         "rows": [[*key, *(v.hex() for v in g)] for key, g in zip(keys, gross)]}
        calibrations.append(FoldCalibration(
            fold, train_ids, evaluation_ids, keys,
            digest(canonical_bytes(row_payload)), digest(canonical_bytes(gross_payload)),
            EmpiricalPrior(gross)))
    return CalibrationBundle(digest(data), len(data), scenario_count, periods, tuple(calibrations))
