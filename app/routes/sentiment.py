"""Stakeholder feedback sentiment analysis dashboard.

Runs the lexicon-based sentiment analyzer over narrative stakeholder feedback
stored in the system (Feedback documents and free-text survey answers) and
presents an interpretable dashboard: sentiment distribution, key matched
terms, per-item results, and an interpretation that links the findings to
institutional decision-making.
"""
import json

from flask import Blueprint, render_template
from flask_login import login_required

from app import db
from app.models import Document, SurveySubmission

from app.ml.sentiment import analyze_sentiment, summarize

sentiment_bp = Blueprint("sentiment", __name__)


def _feedback_documents():
    """Return (title, text) pairs from documents labeled as feedback."""
    docs = (
        Document.query
        .filter(
            db.or_(
                Document.category == "Stakeholder Feedback",
                Document.predicted_category == "Stakeholder Feedback",
            )
        )
        .all()
    )
    entries = []
    for d in docs:
        text = (d.content or "").strip()
        if text:
            entries.append({"source": "Document", "title": d.title or "Feedback", "text": text})
    return entries


def _survey_feedback():
    """Return free-text ('text') question answers across all survey submissions."""
    surveys_rows = (
        db.session.query(SurveySubmission.answers)
        .all()
    )
    entries = []
    for (raw_answers,) in surveys_rows:
        try:
            data = json.loads(raw_answers or "{}")
        except ValueError:
            continue
        for value in data.values():
            if isinstance(value, str) and value.strip():
                entries.append({"source": "Survey", "title": "Survey Response", "text": value.strip()})
    return entries


def _gather():
    entries = _feedback_documents() + _survey_feedback()
    results = []
    for e in entries:
        analysis = analyze_sentiment(e["text"])
        analysis.update(e)
        results.append(analysis)
    return results


def _dominant_terms(results):
    pos_terms, neg_terms = {}, {}
    for r in results:
        for w in r.get("positive_matches", []):
            pos_terms[w] = pos_terms.get(w, 0) + 1
        for w in r.get("negative_matches", []):
            neg_terms[w] = neg_terms.get(w, 0) + 1
    top_pos = sorted(pos_terms.items(), key=lambda kv: -kv[1])[:5]
    top_neg = sorted(neg_terms.items(), key=lambda kv: -kv[1])[:5]
    return top_pos, top_neg


@sentiment_bp.route("/sentiment")
@login_required
def dashboard():
    results = _gather()
    summary = summarize(results)
    top_pos, top_neg = _dominant_terms(results)

    # Quick structured note puts the numbers into decision context.
    if summary["total"] == 0:
        insight = "No stakeholder feedback has been recorded yet. Add feedback documents or survey text responses to begin sentiment analysis."
    else:
        insight = "Stakeholder feedback is predominantly {dominant}. The system can use this signal to prioritize improvements and report impact.".format(
            dominant=summary["dominant"].lower()
        )

    return render_template(
        "sentiment/index.html",
        results=results,
        summary=summary,
        top_pos=top_pos,
        top_neg=top_neg,
        insight=insight,
    )