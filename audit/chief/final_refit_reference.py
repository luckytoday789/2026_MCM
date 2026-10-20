"""Generated-only reference for a future all-development refit, not production code.

No project imports, competition inputs, path overrides, fitting API or final access.
--write creates new expected artifacts; --check reconstructs and compares bytes.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

FIELDS = ('scenario_id', 'period', 'equity_return', 'bond_return',
          'bill_proxy_return', 'inflation')
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'audit/chief/final-refit-reference'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fixture(scenarios, periods):
    # Exact dyadic nominal observations; positive rational real factors.
    support = ((0., 0., 0., 0.), (.25, 0., -.125, .25),
               (-.25, .125, 0., -.125), (-.5, .25, .125, 0.))
    return [(s, t, *support[(s - 1) % 4])
            for s in range(1, scenarios + 1) for t in range(1, periods + 1)]

def csv_bytes(rows, newline='\n'):
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator=newline)
    writer.writerow(FIELDS)
    writer.writerows(rows)
    return out.getvalue().encode('ascii')

def identities(rows):
    nominal = {'schema': 'training-annual-simple-v1', 'fields': list(FIELDS),
               'rows': [[s, t, *(float(v).hex() for v in values)]
                        for s, t, *values in rows]}
    # The ordinary binary64 operation order is an identity reference. The
    # separate Fraction path below supplies exact mathematical expectations.
    gross = {'schema': 'training-real-gross-v1', 'asset_order': list(FIELDS[2:5]),
             'rows': [[s, t, *[((1. + float(r)) / (1. + float(values[3]))).hex()
                       for r in values[:3]]] for s, t, *values in rows]}
    return {'training_rows_sha256': sha(canonical(nominal)),
            'real_gross_sha256': sha(canonical(gross))}

def rational_gross(rows):
    return [tuple((1 + Fraction(r)) / (1 + Fraction(values[3]))
                  for r in values[:3]) for _, _, *values in rows]

def moment(weights, prior, recent):
    def inverse_cube(g):
        return 1 / sum(w * v for w, v in zip(weights, g)) ** 3
    p = sum(map(inverse_cube, prior), Fraction()) / len(prior)
    return (15 * p + sum(map(inverse_cube, recent), Fraction())) / (15 + len(recent))

def decimal_ce(m):
    with localcontext() as ctx:
        ctx.prec = 90
        return str(ctx.power(Decimal(m.denominator) / Decimal(m.numerator),
                             Decimal(1) / Decimal(3)))

def build():
    rows = fixture(4, 3)
    prior = rational_gross(rows)
    recent = rational_gross(fixture(5, 1))
    targets = {'equity': (1, 0, 0), 'bond': (0, 1, 0), 'bills': (0, 0, 1),
               'equal': (Fraction(1, 3),) * 3,
               'conservative': (Fraction(15, 100), Fraction(20, 100), Fraction(65, 100)),
               'growth': (Fraction(60, 100), Fraction(30, 100), Fraction(10, 100))}
    values = []
    for name, target in targets.items():
        weights = tuple(Fraction(x) for x in target)
        for n in (0, 1, 5):
            m = moment(weights, prior, recent[:n])
            values.append({'target': name, 'weights_rational': [str(x) for x in weights],
                           'recent_count': n, 'prior_support_count': len(prior),
                           'prior_total_mass': str(Fraction(15, 15 + n)),
                           'mass_per_training_row': str(Fraction(15, (15 + n) * len(prior))),
                           'mass_per_recent_row': None if n == 0 else str(Fraction(1, 15 + n)),
                           'inverse_cube_moment_numerator': str(m.numerator),
                           'inverse_cube_moment_denominator': str(m.denominator),
                           'ce_decimal_90_digits': decimal_ce(m)})
    full = fixture(120, 30)
    shape = {'origin': 'generated_repeating_dyadic_fixture_not_competition_data',
             'scenario_ids': list(range(1, 121)), 'periods': 30,
             'training_row_count': len(full), 'annual_weight': '1 / 3600',
             'input_sha256': sha(csv_bytes(full)), **identities(full)}
    lf, crlf = csv_bytes(rows), csv_bytes(rows, '\r\n')
    # Same parsed values, distinct exact input bytes; never normalize the
    # production file before matching its locked original byte digest.
    parsed_lf = list(csv.reader(io.StringIO(lf.decode('ascii'))))
    parsed_crlf = list(csv.reader(io.StringIO(crlf.decode('ascii'))))
    zero = [(1, 1, 0., 0., 0., 0.)]
    scale = [(1, 1, .25, .25, .25, .25)]
    minus_zero = [(1, 1, -0., 0., 0., 0.)]
    z, a, m = identities(zero), identities(scale), identities(minus_zero)
    all_m = moment(tuple(Fraction(x) for x in targets['growth']), prior, [])
    leave_one_out = rational_gross([r for r in rows if r[0] != 1])
    omitted_m = moment(tuple(Fraction(x) for x in targets['growth']), leave_one_out, [])
    invariants = {
        'LF_CRLF_input_hashes_differ': sha(lf) != sha(crlf),
        'LF_CRLF_parsed_rows_equal': parsed_lf == parsed_crlf,
        'nominal_change_same_real_vectors': z['training_rows_sha256'] != a['training_rows_sha256']
            and z['real_gross_sha256'] == a['real_gross_sha256'],
        'signed_zero_preserved_in_nominal_identity': z['training_rows_sha256'] != m['training_rows_sha256']
            and z['real_gross_sha256'] == m['real_gross_sha256'],
        'all_training_vs_fold_subset_moment_differs': all_m != omitted_m,
        'full_shape_is_3600_rows_not_2700': len(full) == 3600 and len(full) != 2700,
        'all_18_exact_moments_positive': len(values) == 18 and all(
            int(v['inverse_cube_moment_numerator']) > 0 for v in values),
    }
    if not all(invariants.values()):
        raise ValueError('generated reference invariant failed')
    expected = {'schema_version': 1, 'scope': 'future_refit_generated_reference_only',
                'independent_implementation_acceptance': False, 'competition_inputs_read': False,
                'production_execution_authorized': False, 'final_data_open': False,
                'fixture': {'scenarios': 4, 'periods': 3, 'training_row_count': 12,
                            'input_sha256': sha(lf), **identities(rows)},
                'full_shape_generated_only': shape, 'scalar_expectations': values,
                'invariants': invariants,
                'numerical_note': 'Exact rational gross factors and mathematical weights; Decimal roots at 90-digit precision. Binary64 implementation comparisons require documented tolerances, not exact decimal equality.'}
    return {'fixture.csv': lf, 'expected.json': json.dumps(expected, indent=2, allow_nan=False).encode('utf-8') + b'\n'}

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--write', action='store_true')
    action.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build()
    if args.write:
        OUTPUT.mkdir(exist_ok=False)
        for name, data in outputs.items():
            with (OUTPUT / name).open('xb') as stream:
                stream.write(data)
    else:
        for name, data in outputs.items():
            if (OUTPUT / name).read_bytes() != data:
                raise ValueError('generated reference differs: ' + name)
    print(json.dumps({'reference_reconstructed': True, 'mode': 'write' if args.write else 'check',
                      'scalar_expectations': 18, 'generated_invariants': 7,
                      'artifacts_sha256': {n: sha(d) for n, d in outputs.items()},
                      'competition_inputs_read': False, 'implementation_tested': False}))

if __name__ == '__main__':
    main()
