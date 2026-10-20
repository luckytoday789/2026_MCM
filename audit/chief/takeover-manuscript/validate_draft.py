"""Read-only evidence/layout audit of the chief's incomplete local draft.

This checks accepted-value transcription and mechanical bounds, not policy
selection, final outcomes or independent manuscript acceptance.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "report"))
from build_submission import assemble, sha, canonical


def check(output):
    from pypdf import PdfReader
    text, current = assemble()
    saved = json.loads((output / "build-provenance.json").read_bytes())
    assert not saved["private_identity_access"]
    assert (output / "expanded-draft.md").read_text(encoding="utf-8") == text
    for key in ("source_hashes", "pending_slots", "numeric_paragraph_mappings",
                "prose_result_claim_checks", "word_count",'doubled_fee_provenance',
                'doubled_fee_prose_checks','primary_current_acceptances','slot_status','completed_slots'):
        assert saved[key] == current[key], key
    assert len(saved["pending_slots"]) == len(set(saved["pending_slots"]))
    assert saved['pending_slots']==[name for name,record in saved['slot_status'].items()
                                   if record['state']!='completed']
    assert 'SENSITIVITY_RESULTS' not in saved['pending_slots']
    assert 'SENSITIVITY_RESULTS' in saved['completed_slots']
    assert saved['slot_status']['SENSITIVITY_RESULTS']['state']=='completed'
    assert 'SENSITIVITY_RECOMMENDATION_IMPACT' in saved['pending_slots']
    assert not saved["submission_ready"] and not saved["final_outcomes_accessed"]
    pdf = output / "SafeInvest-incomplete-draft.pdf"
    assert saved["pdf_checks"]["pdf_sha256"] == sha(pdf.read_bytes())
    reader = PdfReader(pdf); sizes = []; texts = []
    for page in reader.pages:
        texts.append(page.extract_text(visitor_text=lambda t, cm, tm, font, size:
            sizes.append(float(size)) if t.strip() else None))
        assert abs(float(page.mediabox.width)-595.2756) < .02
        assert abs(float(page.mediabox.height)-841.8898) < .02
        assert "INCOMPLETE DRAFT" in texts[-1]
    all_text = " ".join(texts)
    assert min(sizes) >= 11 and len(reader.pages) <= 10
    for slot in saved["pending_slots"]:
        if saved['slot_status'][slot]['pending_marker_present']:
            assert "PENDING " + slot in all_text
    assert "scenario is 114" in all_text
    assert "maximum drawdown 52.61%" in all_text
    assert "terminal real wealth 357.95" in all_text
    assert "not customer recommendations" in all_text
    assert '28.26%' in all_text and '42.02%' in all_text and '8.33%' in all_text
    assert saved['doubled_fee_provenance']['producer_commit']=='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18'
    return {"status": "passed", "kind": "chief_preparation_check_not_independent_acceptance",
        "pages": len(reader.pages), "minimum_font_pt": min(sizes),
        "word_count": saved["word_count"], "numeric_paragraphs_mapped": len(saved["numeric_paragraph_mappings"]),
        "pending_slots": saved["pending_slots"], "submission_ready": False,
        "simulation_rerun": False, "final_outcomes_read": False,
        "source_generators_replayed_read_only": ["build_primary_note.build", "build_baseline_note.build"],
        "pdf_sha256": saved["pdf_checks"]["pdf_sha256"]}


if __name__ == "__main__":
    print(json.dumps(check(Path(sys.argv[1])), indent=2))
