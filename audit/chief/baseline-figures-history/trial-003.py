"""Export source-bound baseline figures without simulations or final-data reads."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "7652410d73425371110784ef5fa97c03470a074e"
REVIEW = "818af5d65bd8a271962d848dd552bd39ca561f68"
PREFIX = "results/development/HY3-003/"
PINS = {
    "summary.csv": "965c3ac513f63de31830603ab968f5c6e99c6ceb763515b99753282d8c3a4994",
    "annual_ledgers.csv": "b2e93442391d2a7cec4bdfe79b397c14c311cc229e2e6c3d82d2dd04199d470a",
}
POLICIES = ("bills_keep", "equal_weight_annual", "equal_weight_buy_hold")
LABELS = ("Bills held", "Annual thirds", "Initial thirds held")
COLORS = ("#333333", "#0072B2", "#A94400")
STYLES = (":", "-", "--")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def load_sources():
    queue = json.loads((ROOT / "ops/queue.json").read_bytes())
    for task, sha in (("HY3-003", COMMIT), ("SOL-008", REVIEW)):
        entry = next(x for x in queue["tasks"] if x["id"] == task)
        assert entry["state"] == "accepted" and entry["reviewed_commit"] == sha
    receipt = json.loads(git_blob(COMMIT, "handoff/HY3-003/result.json"))
    rows = {}
    for name, pin in PINS.items():
        path = PREFIX + name
        raw = git_blob(COMMIT, path)
        assert digest(raw) == pin == receipt["artifacts_sha256"][path], path
        assert (ROOT / path).read_bytes() == raw, path
        rows[name] = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    summaries = rows["summary.csv"]
    assert len(summaries) == 15
    assert {(r["policy"], int(r["horizon"])) for r in summaries} == {
        (p, h) for p in POLICIES for h in (5, 6, 15, 25, 30)}
    assert all(r["split"] == "development" and r["scenario_count"] == "120"
               for r in summaries)
    ledgers = rows["annual_ledgers.csv"]
    assert len(ledgers) == 10800
    assert {(r["policy"], int(r["scenario_id"]), int(r["year"])) for r in ledgers} == {
        (p, s, y) for p in POLICIES for s in range(1, 121) for y in range(1, 31)}
    assert all(r["split"] == "development" for r in ledgers)
    common = {r["policy"]: r for r in summaries if r["horizon"] == "30"}
    return common, ledgers


def event_paths(common, ledgers):
    selected = common["equal_weight_annual"]
    scenario = int(selected["severe_scenario_id"])
    output = []
    for policy in POLICIES:
        records = sorted((r for r in ledgers if r["policy"] == policy
                          and int(r["scenario_id"]) == scenario), key=lambda r: int(r["year"]))
        path = [{"policy": policy, "scenario_id": scenario, "event_index": 0,
                 "year": 0, "stage": "initial", "elapsed_years": 0, "real_wealth": 100.0}]
        for row in records:
            year = int(row["year"])
            for stage, elapsed, field in (("post_fee", year - 1, "real_wealth_after_fee"),
                                          ("end", year, "real_wealth_end")):
                value = float(row[field])
                assert math.isfinite(value) and value > 0
                path.append({"policy": policy, "scenario_id": scenario,
                             "event_index": len(path), "year": year, "stage": stage,
                             "elapsed_years": elapsed, "real_wealth": value})
        assert len(path) == 61
        output.extend(path)
    annual = [p for p in output if p["policy"] == "equal_weight_annual"]
    peak = annual[0]
    peak_at_loss = trough = peak
    worst = 0.0
    for point in annual:
        if point["real_wealth"] > peak["real_wealth"]:
            peak = point
        loss = 100 * (1 - point["real_wealth"] / peak["real_wealth"])
        if loss > worst:
            worst, peak_at_loss, trough = loss, peak, point
    assert math.isclose(worst, float(selected["severe_max_real_drawdown_pct"]), abs_tol=1e-10, rel_tol=0)
    for prefix, point in (("peak", peak_at_loss), ("trough", trough)):
        assert point["year"] == int(selected[f"severe_drawdown_{prefix}_year"])
        assert point["stage"] == selected[f"severe_drawdown_{prefix}_kind"]
    assert annual[-1]["real_wealth"] == float(selected["severe_terminal_real_wealth"])
    return output, peak_at_loss, trough, worst


def save_formats(fig, name, output):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    for label in fig.findobj(matplotlib.text.Text):
        if label.get_visible() and label.get_text():
            box = label.get_window_extent(renderer)
            # Out-of-range tick Text objects exist but are not drawn; axes bounds below use the actual interval.
            assert label.get_fontsize() >= 11
    for ax in fig.axes:
        box = ax.get_tightbbox(renderer)
        assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= bounds.x1 + 1 and box.y1 <= bounds.y1 + 1, "axes extent"
    for fmt in ("png", "svg", "pdf"):
        buffer = io.BytesIO()
        metadata = {"Creator": "SafeInvest report/build_baseline_figures.py"}
        if fmt == "png":
            metadata = {"Software": "SafeInvest / Matplotlib " + matplotlib.__version__}
        elif fmt == "svg":
            metadata["Date"] = None
        else:
            metadata.update({"CreationDate": None, "ModDate": None})
        fig.savefig(buffer, format=fmt, dpi=300, facecolor="white", transparent=False,
                    metadata=metadata)
        output[name + "." + fmt] = buffer.getvalue()
    plt.close(fig)


def render(common, points, peak, trough, worst):
    output = {}
    style = {"font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 11,
             "axes.labelsize": 11, "xtick.labelsize": 11, "ytick.labelsize": 11,
             "legend.fontsize": 11, "svg.fonttype": "none", "svg.hashsalt": "safeinvest-baseline-v1",
             "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False}
    with plt.rc_context(style):
        fig, axes = plt.subplots(2, 1, figsize=(180 / 25.4, 126 / 25.4), layout="constrained")
        panels = (("median_growth_pct", "p10_growth_pct", "Real CAGR (% per year)", "p10", "A  Growth"),
                  ("median_loss_pct", "p90_loss_pct", "Maximum real drawdown (%)", "p90", "B  Large loss"))
        for ax, (center, tail, xlabel, tail_label, title) in zip(axes, panels):
            values = []
            for j, policy in enumerate(POLICIES):
                a, b = float(common[policy][center]), float(common[policy][tail])
                values.extend((a, b))
                ax.plot([a, b], [j, j], color=COLORS[j], linewidth=1.2)
                ax.plot(a, j, "o", color=COLORS[j], markersize=7)
                ax.plot(b, j, "|", color=COLORS[j], markersize=13, markeredgewidth=2)
            ax.set(yticks=range(3), yticklabels=LABELS, ylim=(2.6, -0.6), xlabel=xlabel)
            ax.set_xlim(min(0, min(values)), max(values) * 1.12)
            ax.set_title(title, loc="left", fontweight="bold")
            ax.grid(axis="x", color="#dddddd", linewidth=.5)
            ax.set_axisbelow(True)
            ax.legend(handles=[Line2D([], [], color="#222222", marker="o", linestyle="None", label="Median"),
                               Line2D([], [], color="#222222", marker="|", markersize=13, linestyle="None", label=tail_label)],
                      loc="upper center", bbox_to_anchor=(.5, 1.26), ncol=2, frameon=False)
        save_formats(fig, "baseline-h30-summary", output)
        fig, ax = plt.subplots(figsize=(180 / 25.4, 112 / 25.4), layout="constrained")
        for policy, label, color, line in zip(POLICIES, LABELS, COLORS, STYLES):
            path = [p for p in points if p["policy"] == policy]
            ax.plot([p["elapsed_years"] for p in path], [p["real_wealth"] for p in path],
                    color=color, linestyle=line, linewidth=1.6, label=label)
        for point, marker in ((peak, "o"), (trough, "v")):
            ax.plot(point["elapsed_years"], point["real_wealth"], marker=marker,
                    color=COLORS[1], markersize=8, linestyle="None")
        ax.annotate(f"Annual thirds: {worst:.2f}% loss\npeak: year {peak['year']} end\ntrough: year {trough['year']} post-fee",
                    xy=(trough["elapsed_years"], trough["real_wealth"]), xytext=(10, 12),
                    arrowprops={"arrowstyle": "->", "color": "#222222"}, fontsize=11)
        ax.axhline(100, color="#999999", linewidth=.7, zorder=0)
        ax.set(xlabel="Elapsed years (fees precede each year's returns)",
               ylabel="Real wealth (initial purchasing power = 100)", xlim=(0, 30), ylim=(0, None))
        ax.set_title(f"Annual thirds' severe development scenario: {points[0]['scenario_id']}", loc="left", fontweight="bold")
        ax.legend(loc="upper left", frameon=False)
        ax.grid(axis="y", color="#dddddd", linewidth=.5)
        ax.set_axisbelow(True)
        save_formats(fig, "baseline-h30-severe-path", output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Rebuild in memory and require unchanged files")
    args = parser.parse_args()
    common, ledgers = load_sources()
    points, peak, trough, worst = event_paths(common, ledgers)
    outputs = render(common, points, peak, trough, worst)
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=list(points[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(points)
    outputs["baseline-h30-severe-points.csv"] = table.getvalue().encode()
    exports = {}
    for name, raw in outputs.items():
        info = {"sha256": digest(raw), "bytes": len(raw)}
        if name.endswith(".png"):
            with Image.open(io.BytesIO(raw)) as im:
                info.update({"pixels": list(im.size), "dpi": list(im.info["dpi"]), "mode": im.mode})
                assert min(im.info["dpi"]) >= 299
                assert im.getchannel("A").getextrema() == (255, 255)
        if name.endswith(".pdf"):
            pdf = PdfReader(io.BytesIO(raw))
            assert len(pdf.pages) == 1
            box = pdf.pages[0].mediabox
            info["millimeters"] = [float(box.width) * 25.4 / 72, float(box.height) * 25.4 / 72]
            assert abs(info["millimeters"][0] - 180) < .001
        exports[name] = info
    manifest = {
        "schema_version": 1, "kind": "development_baseline_report_figures",
        "source_commit": COMMIT, "independent_review_commit": REVIEW,
        "source_hashes": {PREFIX + k: v for k, v in PINS.items()},
        "generator_sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
        "split": "development", "scenario_count": 120, "horizon": 30, "fee_rate": .0025,
        "summary_rows": [common[p] for p in POLICIES],
        "path_selection": "Annual equal-weight baseline's existing greatest-loss scenario; other references use that same scenario",
        "path_point_count": len(points), "peak": peak, "trough": trough, "loss_pct": worst,
        "time_axis": "initial=0; year-t post_fee at t-1, year-t end at t; vertical jumps retain fees",
        "transforms": ["Filter the three accepted H30 summary rows", "Copy every initial/post-fee/end point on selected scenario", "Join successive observations with unsmoothed straight segments; no intra-year observations implied"],
        "quantiles": "Descriptive linear scenario quantiles, not confidence intervals",
        "minimum_font_points_at_180mm": 11,
        "checks": {"exact_pins_and_queue_acceptance": True, "complete_source_key_coverage": True,
                   "selected_path_loss_and_locations_reconstructed": True, "text_inside_canvas": True,
                   "opaque_png_at_300dpi": True, "pdf_width_180mm": True},
        "outputs": exports, "simulation_rerun": False, "final_outcomes_read": False,
        "scope": "Chief-prepared figure transforms; final manuscript review and layout check still required",
    }
    outputs["baseline-figures-provenance.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    target = ROOT / "report/figures"
    if not args.check:
        target.mkdir(exist_ok=True)
    for name, raw in outputs.items():
        path = target / name
        if args.check or path.exists():
            assert path.read_bytes() == raw, name + ": mismatch (no overwrite)"
        else:
            path.write_bytes(raw)
    print(json.dumps({"status": "passed", "read_only": args.check, "summary_rows": 3,
                      "path_points": len(points), "selected_scenario": points[0]["scenario_id"],
                      "severe_loss_pct": worst, "exports": len(outputs), "simulation_rerun": False}))


if __name__ == "__main__":
    main()
