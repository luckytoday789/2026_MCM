"""Chief figure checks using saved metrics and stdlib quantiles, not plotting code."""
import argparse
import csv
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
SHA = "7652410d73425371110784ef5fa97c03470a074e"
PREFIX = "results/development/HY3-003/"
PINS = {
    "summary.csv": "965c3ac513f63de31830603ab968f5c6e99c6ceb763515b99753282d8c3a4994",
    "scenario_metrics.csv": "afabf571d8c7d224bd83f836033fe4c4907a05fc15a2e8614c8ae09d803f100c",
    "annual_ledgers.csv": "b2e93442391d2a7cec4bdfe79b397c14c311cc229e2e6c3d82d2dd04199d470a",
}


def source(name):
    raw = subprocess.check_output(["git", "show", SHA + ":" + PREFIX + name], cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest() == PINS[name]
    return list(csv.DictReader(io.StringIO(raw.decode())))


def quantile(values, p):
    values = sorted(values)
    index = Fraction(len(values) - 1) * p
    lower = index.numerator // index.denominator
    return float(Fraction.from_float(values[lower]) * (1 - (index - lower)) +
                 Fraction.from_float(values[math.ceil(index)]) * (index - lower))


def build():
    summaries, metrics, ledgers = source("summary.csv"), source("scenario_metrics.csv"), source("annual_ledgers.csv")
    summary_checks = []
    for row in (r for r in summaries if r["horizon"] == "30"):
        selected = [m for m in metrics if m["horizon"] == "30" and m["policy"] == row["policy"]]
        assert len(selected) == 120
        growth = [float(r["net_real_cagr_pct"]) for r in selected]
        loss = [float(r["max_real_drawdown_pct"]) for r in selected]
        computed = {"median_growth_pct": statistics.median(growth),
                    "p10_growth_pct": quantile(growth, Fraction(1, 10)),
                    "median_loss_pct": statistics.median(loss),
                    "p90_loss_pct": quantile(loss, Fraction(9, 10))}
        for key, value in computed.items():
            assert math.isclose(value, float(row[key]), abs_tol=1e-12, rel_tol=0)
        severe = min(selected, key=lambda r: (-float(r["max_real_drawdown_pct"]), int(r["scenario_id"])))
        assert severe["scenario_id"] == row["severe_scenario_id"]
        summary_checks.append({"policy": row["policy"], "computed": computed,
                               "severe_scenario_id": int(severe["scenario_id"])})
    target = ROOT / "report/figures"
    points = list(csv.DictReader(io.StringIO((target / "baseline-h30-severe-points.csv").read_text())))
    assert len(points) == 183
    lookup = {(r["policy"], r["scenario_id"], r["year"]): r for r in ledgers}
    for point in points:
        assert point["scenario_id"] == "5"
        if point["stage"] == "initial":
            assert point["year"] == point["event_index"] == point["elapsed_years"] == "0"
            assert float(point["real_wealth"]) == 100
        else:
            row = lookup[point["policy"], point["scenario_id"], point["year"]]
            field = {"post_fee": "real_wealth_after_fee", "end": "real_wealth_end"}[point["stage"]]
            assert float(point["real_wealth"]) == float(row[field])
            year = int(point["year"])
            assert int(point["elapsed_years"]) == year - int(point["stage"] == "post_fee")
            assert int(point["event_index"]) == 2 * year - int(point["stage"] == "post_fee")
    annual = [p for p in points if p["policy"] == "equal_weight_annual"]
    peak = Fraction.from_float(float(annual[2]["real_wealth"]))
    trough = Fraction.from_float(float(annual[15]["real_wealth"]))
    rational_loss = float(100 * (1 - trough / peak))
    assert math.isclose(rational_loss, 50.87762271755738, abs_tol=1e-12, rel_tol=0)
    fonts = []
    for name in ("baseline-h30-summary.pdf", "baseline-h30-severe-path.pdf"):
        pdf = PdfReader(target / name)
        sizes = []
        def visitor(text, cm, tm, font, size):
            if text.strip():
                sizes.append(size)
        pdf.pages[0].extract_text(visitor_text=visitor)
        assert sizes and min(sizes) >= 11, name
        for ref in pdf.pages[0]["/Resources"]["/Font"].values():
            font = ref.get_object()
            child = font["/DescendantFonts"][0].get_object()
            assert "/FontFile2" in child["/FontDescriptor"].get_object()
        fonts.append({"file": name, "min_font_points": min(sizes), "embedded_truetype": True})
    def contrast(color):
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        lum = sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
        return 1.05 / (lum + .05)
    ratios = {c: contrast(c) for c in ("#333333", "#0072B2", "#A94400")}
    assert min(ratios.values()) >= 3
    return {"schema_version": 1, "source_commit": SHA,
            "source_pins": PINS, "summary_statistics_checked": 12,
            "summary_checks": summary_checks, "all_plotted_observations_checked": 183,
            "rational_severe_loss_pct": rational_loss, "pdf_fonts": fonts,
            "data_color_contrast_against_white": ratios,
            "scope": "Chief checks; independent Sol figure/wording review still required. Contrast checks do not certify accessibility.",
            "simulation_rerun": False, "final_outcomes_read": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = build()
    destination = ROOT / "audit/chief/baseline-figures-validation.json"
    if args.check:
        assert json.loads(destination.read_bytes()) == result
    else:
        with destination.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
    print(json.dumps({"status": "passed", "read_only": args.check, "summary_statistics": 12,
                      "path_observations": 183, "pdfs": 2}))


if __name__ == "__main__":
    main()
