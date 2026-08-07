"""Stakeholder feedback sentiment analysis.

A lightweight, lexicon-based sentiment analyzer (no external dependencies, no
trained model required). It scores the polarity of narrative feedback text as
Positive, Neutral, or Negative and exposes an aggregate summary so the system
can interpret stakeholder sentiment across feedback documents.

This complements the document-type / domain classifiers: those categorize WHAT
a document is, while this module measures HOW stakeholders feel about it.
"""
import re

from app.ml.preprocess import clean_text

POSITIVE = frozenset(
    """good great excellent wonderful fantastic superb outstanding amazing
    impressive appreciate appreciated appreciated thanks gratitude helpful
    valuable effective useful love loved best benefit beneficial success
    successful improved improving satisfied satisfying satisfaction excellent
    quality comfortable practical practical support supportive committed strong
    coordination effective skillful skilled well praise praised positive
    favorable recommend recommended fruitful gained gain advantage
    convenient welcoming friendly kind generous proud better helped helpful
    glad happy thrive liked enjoyed pleased works""".split()
)

NEGATIVE = frozenset(
    """
    bad poor terrible awful disappointing disappointed unsatisfactory
    unacceptable weak fail failed failing lack lacking concern concerns
    problem problems issue issues difficult hard complaint complaints
    insufficient not enough not improvement lacks delay delays
    late shortage missing unclear confusing inconvenient uncomfortable
    regret improve need longer additional unavailable overdue
    unwilling refuse rejected violated ignored""".split()
)

_NEGATION = {
    "no", "not", "never", "hardly", "barely", "doesn't", "don't",
    "didn't", "isn't", "aren't", "wasn't", "weren't", "cannot", "can't",
    "won't", "wouldn't", "shouldn't", "lack", "lacks", "lacking",
}

_INTENSIFIERS = {
    "very": 1.5, "so": 1.4, "really": 1.4, "extremely": 1.8,
    "quite": 1.2, "highly": 1.6, "absolutely": 1.6, "fairly": 1.1,
    "somewhat": 0.7, "slightly": 0.7, "more": 1.3, "most": 1.5,
}

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _tokens(text):
    return clean_text(text).split()


def analyze_sentiment(text):
    """    Score the sentiment of a piece of feedback text.

    Returns a dict with a numeric ``score`` in [-1, 1], a ``label`` of
    ("Positive", "Neutral", "Negative"), and the matched positive/negative
    keywords for transparency.

    Simple algorithm: iterate tokens, flip polarity when a negation word
    precedes a sentiment word within a short window, and amplify with a
    preceding intensifier.
    """
    tokens = _tokens(text)
    score = 0.0
    matched_pos, matched_neg = [], []

    for i, token in enumerate(tokens):
        # Locate a sentiment word and check the 2 tokens before it.
        target = None
        if token in POSITIVE:
            target = token
            matched_pos.append(token)
        elif token in NEGATIVE:
            target = token
            matched_neg.append(token)
        if target is None:
            continue

        weight = 1.0
        negated = False
        for offset in (1, 2):
            j = i - offset
            if j < 0:
                break
            prev = tokens[j]
            if prev in _NEGATION:
                negated = True
            if prev in _INTENSIFIERS:
                weight *= _INTENSIFIERS[prev]

        value = weight if target in POSITIVE else -weight
        if negated:
            value = -value
        score += value

    if score > 0:
        label = "Positive"
    elif score < 0:
        label = "Negative"
    else:
        label = "Neutral"

    # Normalize into [-1, 1]
    magnitude = float(len(matched_pos) + len(matched_neg))
    normalized = max(-1.0, min(1.0, score / magnitude if magnitude else 0.0))

    return {
        "label": label,
        "score": round(normalized, 3),
        "positive_matches": matched_pos,
        "negative_matches": matched_neg,
    }


def summarize(feedbacks):
    """Aggregate a list of sentiment results (dicts from analyze_sentiment).

    Returns counts per label, the mean normalized score, and simple narrative
    pointers (e.g. dominant sentiment) useful for an interpretation section.
    """
    counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    total_score = 0.0
    n = len(feedbacks)
    for fb in feedbacks:
        label = fb.get("label", "Neutral")
        counts[label] = counts.get(label, 0) + 1
        total_score += fb.get("score", 0.0)

    mean = round(total_score / n, 3) if n else 0.0
    if n == 0:
        dominant = None
    else:
        dominant = max(counts, key=counts.get)

    return {
        "total": n,
        "counts": counts,
        "mean_score": mean,
        "dominant": dominant,
        "pos_pct": round(counts["Positive"] * 100 / n, 1) if n else 0.0,
        "neg_pct": round(counts["Negative"] * 100 / n, 1) if n else 0.0,
        "neu_pct": round(counts["Neutral"] * 100 / n, 1) if n else 0.0,
    }