"""Generated fixtures only; these chief checks are not independent acceptance."""

import csv
from dataclasses import FrozenInstanceError
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.policy_calibration import build_synthetic_calibrations, fold_id

FIELDS = ("scenario_id", "period", "equity_return", "bond_return", "bill_proxy_return", "inflation")


def fixture(scenarios=8, periods=3):
    return [dict(zip(FIELDS, (s, t, .1, .02, 0., .02)))
            for s in range(1, scenarios+1) for t in range(1, periods+1)]


def encode(rows, newline="\n"):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator=newline)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(rows=None, scenarios=8, periods=3):
    return build_synthetic_calibrations(encode(rows if rows is not None else fixture(scenarios, periods)),
                                        scenario_count=scenarios, periods=periods)


class CalibrationTests(unittest.TestCase):
    def test_four_fold_exclusion_and_complete_keys(self):
        bundle = build()
        evaluation_ids = []
        for f, calibration in enumerate(bundle.folds):
            evaluation = tuple(s for s in range(1,9) if (s-1)%4 == f)
            training = tuple(s for s in range(1,9) if (s-1)%4 != f)
            self.assertEqual(calibration.evaluation_ids, evaluation)
            self.assertEqual(calibration.training_ids, training)
            self.assertFalse(set(training) & set(evaluation))
            self.assertEqual(calibration.training_keys, tuple((s,t) for s in training for t in range(1,4)))
            self.assertEqual(len(calibration.prior.gross), 18)
            evaluation_ids.extend(evaluation)
        self.assertEqual(sorted(evaluation_ids), list(range(1,9)))

    def test_heldout_perturbation_never_changes_own_fit(self):
        baseline = build()
        changed = fixture()
        for row in changed:
            if (row['scenario_id']-1)%4 == 2:
                row['equity_return'] = -.8
                row['inflation'] = .2
        perturbed = build(changed)
        self.assertNotEqual(perturbed.input_sha256, baseline.input_sha256)
        self.assertEqual(perturbed.folds[2], baseline.folds[2])
        for f in (0,1,3):
            self.assertNotEqual(perturbed.folds[f].prior, baseline.folds[f].prior)
            self.assertNotEqual(perturbed.folds[f].training_rows_sha256, baseline.folds[f].training_rows_sha256)
            self.assertNotEqual(perturbed.folds[f].real_gross_sha256, baseline.folds[f].real_gross_sha256)

    def test_exact_inflation_and_equal_annual_weights(self):
        rows = fixture(scenarios=4, periods=1)
        rows[1].update(equity_return=-.1, bond_return=-.1, bill_proxy_return=-.1, inflation=0.)
        bundle = build(rows, scenarios=4, periods=1)
        for actual, expected in zip(bundle.folds[1].prior.gross[0], (Fraction(55,51), Fraction(1), Fraction(50,51))):
            self.assertAlmostEqual(actual, float(expected), places=14)
        # Held-out scenario 1; training has one .9 and two 1.0 bond gross factors.
        expected_ce = ((Fraction(9,10)**-3 + 2) / 3) ** Fraction(-1,3)
        self.assertAlmostEqual(bundle.folds[0].prior.certainty_equivalent((0,1,0)), float(expected_ce), places=13)

    def test_input_bytes_separate_from_selected_semantic_rows(self):
        rows = fixture()
        lf = build_synthetic_calibrations(encode(rows), scenario_count=8, periods=3)
        crlf = build_synthetic_calibrations(encode(rows, '\r\n'), scenario_count=8, periods=3)
        self.assertNotEqual(lf.input_sha256, crlf.input_sha256)
        self.assertEqual(lf.folds, crlf.folds)
        self.assertEqual(lf.input_sha256, hashlib.sha256(encode(rows)).hexdigest())

    def test_nominal_rows_and_gross_digests_are_distinct(self):
        rows = fixture()
        for row in rows:
            row.update(equity_return=0., bond_return=0., bill_proxy_return=0., inflation=0.)
        a = build(rows)
        for row in rows:
            row.update(equity_return=1., bond_return=1., bill_proxy_return=1., inflation=1.)
        b = build(rows)
        for left,right in zip(a.folds,b.folds):
            self.assertNotEqual(left.training_rows_sha256, right.training_rows_sha256)
            self.assertEqual(left.real_gross_sha256, right.real_gross_sha256)
            self.assertEqual(left.prior, right.prior)

    def test_canonical_payload_matches_independent_explicit_fixture(self):
        rows = fixture(scenarios=4, periods=1)
        bundle = build(rows, scenarios=4, periods=1)
        # Explicit schema/row construction documents the portable byte contract.
        payload = {'schema':'training-annual-simple-v1','fields':list(FIELDS),
                   'rows':[[s,1,float(.1).hex(),float(.02).hex(),float(0).hex(),float(.02).hex()] for s in (2,3,4)]}
        expected = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')).hexdigest()
        self.assertEqual(bundle.folds[0].training_rows_sha256, expected)

    def test_invalid_or_incomplete_grid_is_rejected(self):
        good = fixture()
        cases = [good[:-1], good+[good[-1]], list(reversed(good)), [good[0],*good[:-1]]]
        for rows in cases:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                build(rows)
        for value in (-1., float('nan'), float('inf'), 'True', None):
            rows=fixture()
            rows[-1]['inflation']=value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build(rows)
        for field in ('scenario_id','period'):
            rows=fixture()
            rows[0][field]='01'
            with self.assertRaises(ValueError):
                build(rows)

    def test_schema_and_shape_are_explicit(self):
        data=encode(fixture())
        for corrupted in (data.replace(b'equity_return',b'return'), data.replace(b'inflation',b'inflation,extra'), data.replace(b'1,1,',b'1,1,0,',1)):
            with self.assertRaises(ValueError):
                build_synthetic_calibrations(corrupted,scenario_count=8,periods=3)
        for scenarios,periods in ((0,3),(6,3),(True,3),(8,0),(8,True)):
            with self.assertRaises(ValueError):
                build_synthetic_calibrations(data,scenario_count=scenarios,periods=periods)
        with self.assertRaises(ValueError):
            build_synthetic_calibrations('some/path.csv',scenario_count=8,periods=3)
        for invalid in (0,-1,True,'1',1.5):
            with self.assertRaises(ValueError):
                fold_id(invalid)

    def test_immutable_bundle_and_manifest_copy(self):
        bundle=build()
        with self.assertRaises(FrozenInstanceError):
            bundle.folds[0].fold=99
        manifest=bundle.manifest()
        manifest['folds'][0]['training_scenario_ids'].clear()
        self.assertEqual(len(bundle.folds[0].training_ids),6)
        self.assertEqual(bundle.manifest()['split'],'synthetic')
        self.assertFalse(bundle.manifest()['production_execution_authorized'])
        self.assertEqual(json.loads(json.dumps(bundle.manifest())),bundle.manifest())

    def test_generated_full_shape_has_expected_training_counts(self):
        bundle=build(scenarios=120,periods=30)
        for calibration in bundle.folds:
            self.assertEqual(len(calibration.training_ids),90)
            self.assertEqual(len(calibration.evaluation_ids),30)
            self.assertEqual(len(calibration.training_keys),2700)
            self.assertEqual(len(calibration.prior.gross),2700)


if __name__ == '__main__':
    unittest.main()
