"""Issue #944: Execute Participants and Cases additional tweaks."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_nav_and_cases_page_copy():
    base = (REPO / "frontend" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )
    html = (
        REPO / "frontend" / "templates" / "pages" / "execute_incidents.html"
    ).read_text(encoding="utf-8")
    js = (
        REPO / "frontend" / "static" / "js" / "execute_incidents.js"
    ).read_text(encoding="utf-8")
    assert 'data-rf-execute-view="incidents">Cases</a>' in base
    assert 'href="/execute/incidents"' in base
    assert "{% block title %}Cases{% endblock %}" in html
    assert 'id="rf-hs-title">Cases</h2>' in html
    assert "start a new case" in html
    assert "Search Active and Closed cases by Bib Number" in html
    assert "Start a case" not in html
    assert 'textContent = "Cases"' in js
    assert 'textContent = "Incidents"' not in js


def test_participants_table_and_detail():
    js = (
        REPO / "frontend" / "static" / "js" / "execute_participants.js"
    ).read_text(encoding="utf-8")
    assert "<th>Cases</th>" in js
    assert "rf-hs-pair" in js
    assert 'pairCell("--", true)' in js
    assert 'counts.active + " / " + counts.closed' in js
    assert 'colspan="8"' in js
    assert "VIEW_ICON" in js
    assert 'title="View active case"' in js
    assert '"Start another case"' in js
    assert "Start another case</button>" not in js
    assert "View active case</a>" not in js
    assert '"+1 ("' in js
    assert "PHONE_ICON" in js
    assert "mailto:" in js
    assert "Phone / email" in js
    assert "Emergency contact" in js
    assert "Disclosed conditions" in js
    assert js.index("Phone / email") < js.index("Emergency contact")
    assert js.index("rf-hs-detail-col") < js.index("Disclosed conditions")


def test_cases_queue_and_form_layout():
    js = (
        REPO / "frontend" / "static" / "js" / "execute_incidents.js"
    ).read_text(encoding="utf-8")
    html = (
        REPO / "frontend" / "templates" / "pages" / "execute_incidents.html"
    ).read_text(encoding="utf-8")
    assert "rf-hs-strip-inline-badges" in js
    assert "rf-hs-urgent-mark" in js
    assert "rf-hs-911-mark" in js
    queue = js[js.index("function renderQueue") : js.index("function tile")]
    assert queue.index("Active cases") < queue.index("Closed cases")
    assert queue.index("Closed cases") < queue.index("Search by bib number")
    assert "Start a case" not in js
    render_empty = js[
        js.index("function renderCase") : js.index("function formPayload")
    ]
    assert "rf-hs-case-empty" not in render_empty
    assert "lists.active || [])[0]" in js
    assert "Select all that apply" not in js
    render = js[js.index("function renderCase") : js.index("function formPayload")]
    assert render.index("Reporter's name") < render.index("locationFieldHtml")
    assert render.index("locationFieldHtml") < render.index("Reported problem")
    assert render.index('id="hs-desc"') < render.index("Category")
    assert render.index("Category") < render.index("Care provided")
    assert "Case Updates" in render
    assert "Case History" in render
    assert "rf-hs-history-scroll" in render
    assert "Close Case" in render
    assert 'id="hs-close-modal"' in html
    assert "Record care handoff" in js
    assert "rf-hs-agency-row" in js
    assert "function showCloseModal" in js
    assert "function hideCloseModal" in js
