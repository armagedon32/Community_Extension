"""NLP text preprocessing utilities for document classification."""
import re

STOP_WORDS = frozenset(
    """a about above after again all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here herself him himself
    his how i if in into is it its itself just me more most my myself no nor not of
    off on once only or other our ours ourselves out over own same she should so
    some such than that the their theirs them themselves then there these they this
    those through to too under until up very was we were what when where which while
    who whom why will with would you your yours yourself the and for with this are
    not can its it per an also between including e.g etc""".split()
)


# Domain-agnostic words common to extension documents. Removing these helps
# the classifier focus on discriminative, domain-specific vocabulary.
DOMAIN_GENERIC_WORDS = frozenset(
    """program project outreach activity training support proposal community
    beneficiaries beneficiaries volunteers services implement provide target
    participants amount budget office program report documents activities
    improve area barangay groups needs people new plan social field""".split()
)


def clean_text(text):
    """Lowercase, remove non-alphanumeric characters, and normalize whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    """Split normalized text into tokens."""
    return clean_text(text).split()


def remove_stopwords(tokens):
    """Remove common English stop words."""
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def preprocess(text):
    """Full preprocessing pipeline: clean -> tokenize -> remove stop words."""
    return remove_stopwords(tokenize(clean_text(text)))


def preprocess_domain(text):
    """Preprocess for the domain model: also drops extension-domain generic words."""
    tokens = tokenize(clean_text(text))
    return [
        t for t in tokens
        if t not in STOP_WORDS and t not in DOMAIN_GENERIC_WORDS and len(t) > 1
    ]
