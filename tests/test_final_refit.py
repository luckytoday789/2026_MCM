"""Generated-only independent scalar checks for the all-supplied-row prior."""

import csv
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
from fractions import Fraction
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.final_refit import build_generated_refit
from safeinvest.policy_calibration import FIELDS


def generated(scenarios=4, periods=3):
    support = ((0.,0.,0.,0.), (.25,0.,-.125,.25),
               (-.25,.125,0.,-.125), (-.5,.25,.125,0.))
    return [(s,t,*support[(s-1)%4])
            for s in range(1,scenarios+1) for t in range(1,periods+1)]


def encode(rows, newline="\n"):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator=newline)
    writer.writerow(FIELDS)
    writer.writerows(rows)
    return out.getvalue().encode()


class FinalRefitTests(unittest.TestCase):
    def test_saved_hashes_and_all_eighteen_scalar_references(self):
        directory = ROOT / "audit/chief/final-refit-reference"
        expected = json.loads((directory / "expected.json").read_text())
        refit = build_generated_refit((directory / "fixture.csv").read_bytes(),
                                      scenario_count=4, periods=3)
        for key in ("input_sha256", "training_rows_sha256", "real_gross_sha256"):
            self.assertEqual(getattr(refit,key), expected["fixture"][key])
        recent_rows = generated(5,1)
        recent = tuple(tuple((1+r)/(1+row[-1]) for r in row[2:5]) for row in recent_rows)
        for record in expected["scalar_expectations"]:
            weights = tuple(float(Fraction(v)) for v in record["weights_rational"])
            actual = refit.prior.certainty_equivalent(weights, recent[:record["recent_count"]])
            self.assertAlmostEqual(actual, float(record["ce_decimal_90_digits"]), delta=2e-14)
        # Recompute six moments/roots directly from CSV rational numbers, without
        # calling the saved reference builder or the implementation's CE helper.
        source = list(csv.DictReader(io.StringIO((directory/"fixture.csv").read_text())))
        rational = [tuple((1+Fraction(row[name]))/(1+Fraction(row["inflation"]))
                          for name in FIELDS[2:5]) for row in source]
        for weights in ((Fraction(1),Fraction(0),Fraction(0)),
                        (Fraction(0),Fraction(1),Fraction(0)),
                        (Fraction(0),Fraction(0),Fraction(1)),
                        (Fraction(1,3),)*3,
                        (Fraction(3,20),Fraction(1,5),Fraction(13,20)),
                        (Fraction(3,5),Fraction(3,10),Fraction(1,10))):
            moment = sum(1/sum(w*g for w,g in zip(weights,row))**3 for row in rational)/12
            with localcontext() as context:
                context.prec = 70
                oracle = context.power(Decimal(moment.denominator)/Decimal(moment.numerator),
                                       Decimal(1)/Decimal(3))
            self.assertAlmostEqual(refit.prior.certainty_equivalent(weights), float(oracle), delta=2e-14)

    def test_full_generated_shape_uses_3600_rows_once_and_canonical_hashes(self):
        refit = build_generated_refit(encode(generated(120,30)), scenario_count=120, periods=30)
        expected = json.loads((ROOT/"audit/chief/final-refit-reference/expected.json").read_text())["full_shape_generated_only"]
        self.assertEqual(len(refit.prior.gross),3600)
        self.assertEqual(refit.training_keys,tuple((s,t) for s in range(1,121) for t in range(1,31)))
        for key in ("input_sha256","training_rows_sha256","real_gross_sha256"):
            self.assertEqual(getattr(refit,key),expected[key])
        self.assertEqual(refit.manifest()["annual_weight_value"],1/3600)

    def test_detached_manifest_and_immutable_support(self):
        refit=build_generated_refit(encode(generated()),scenario_count=4,periods=3)
        manifest=refit.manifest()
        manifest["training_row_keys"][0][0]=99
        self.assertEqual(refit.training_keys[0],(1,1))
        self.assertEqual(refit.manifest()["training_row_keys"][0],[1,1])
        self.assertIsNone(refit.manifest()["fold_id"])
        self.assertFalse(refit.manifest()["source_verified"])
        with self.assertRaises(FrozenInstanceError):
            refit.prior.gross=((1.,1.,1.),)

    def test_byte_identity_signed_zero_and_equal_real_support(self):
        rows=generated()
        a=build_generated_refit(encode(rows),scenario_count=4,periods=3)
        b=build_generated_refit(encode(rows,"\r\n"),scenario_count=4,periods=3)
        self.assertNotEqual(a.input_sha256,b.input_sha256)
        self.assertEqual(a.prior,b.prior)
        self.assertEqual(a.real_gross_sha256,b.real_gross_sha256)
        zero=build_generated_refit(encode([(1,1,0.,0.,0.,0.)]),scenario_count=1,periods=1)
        negative=build_generated_refit(encode([(1,1,-0.,0.,0.,0.)]),scenario_count=1,periods=1)
        shifted=build_generated_refit(encode([(1,1,1.,1.,1.,1.)]),scenario_count=1,periods=1)
        self.assertNotEqual(zero.training_rows_sha256,negative.training_rows_sha256)
        self.assertNotEqual(zero.training_rows_sha256,shifted.training_rows_sha256)
        self.assertEqual(zero.real_gross_sha256,negative.real_gross_sha256)
        self.assertEqual(zero.real_gross_sha256,shifted.real_gross_sha256)

    def test_missing_extra_reordered_duplicate_noncanonical_and_invalid_factors(self):
        rows=generated()
        bad=[rows[:-1],rows+[rows[-1]],rows[::-1],rows[:1]+rows[:1]+rows[2:]]
        for values in (float("nan"),float("inf"),-1.,-2.):
            altered=list(rows)
            altered[-1]=(*altered[-1][:2],values,*altered[-1][3:])
            bad.append(altered)
        altered=list(rows); altered[0]=("01",*altered[0][1:]); bad.append(altered)
        for fixture in bad:
            with self.subTest(fixture=fixture[0]),self.assertRaises(ValueError):
                build_generated_refit(encode(fixture),scenario_count=4,periods=3)
        for shape in ((True,3),(0,3),(121,30),(4,True),(4,31)):
            with self.assertRaises(ValueError):
                build_generated_refit(encode(rows),scenario_count=shape[0],periods=shape[1])


if __name__ == "__main__":
    unittest.main()
