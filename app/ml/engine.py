"""NLP + Naive Bayes document classification engine.

Implements the document classification workflow described in the study:
text preprocessing (tokenization, stop-word removal, text normalization),
TF-IDF feature extraction, Naive Bayes model training, prediction, and
evaluation using accuracy, precision, recall, F1-score, and confusion matrix.

Two independent Multinomial Naive Bayes models are trained:
  1. "type"  - classifies the DOCUMENT TYPE (Proposal, Activity Design, MOA, ...)
  2. "domain" - classifies the PROJECT CATEGORY / DOMAIN (Education, Livelihood,
                Governance, Environment, ...)
"""
import json
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

from app.ml.preprocess import preprocess, preprocess_domain

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Persisted artifacts per model kind (type / domain).
_FILES = {
    "type": ("naive_bayes_model.joblib", "vectorizer.joblib", "labels.json"),
    "domain": ("domain_model.joblib", "domain_vectorizer.joblib", "domain_labels.json"),
}


def _preprocess_text(text, kind="type"):
    """Return a space-joined, cleaned string for the vectorizer.

    The domain model additionally drops extension-domain generic words so it
    can focus on discriminative, domain-specific vocabulary.
    """
    prep = preprocess_domain if kind == "domain" else preprocess
    return " ".join(prep(text or ""))


def _vectorizer():
    return TfidfVectorizer(
        lowercase=True,
        min_df=1,
        sublinear_tf=True,
        strip_accents="unicode",
    )


def _paths(kind):
    model_file, vec_file, label_file = _FILES[kind]
    return (
        os.path.join(MODEL_DIR, model_file),
        os.path.join(MODEL_DIR, vec_file),
        os.path.join(MODEL_DIR, label_file),
    )


def _train(texts, labels, kind):
    """Shared training routine for a given model kind."""
    vectorizer = _vectorizer()
    X = vectorizer.fit_transform([_preprocess_text(t, kind) for t in texts])

    X_train, X_test, y_train, y_test = train_test_split(
        X, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # Type classes are roughly balanced (informative priors help); domain classes
    # are imbalanced (uniform priors avoid always predicting the majority class).
    model = MultinomialNB(alpha=1.0, fit_prior=(kind == "type"))
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    unique_labels = sorted(set(labels))
    cm = confusion_matrix(y_test, predictions, labels=unique_labels)
    report = classification_report(
        y_test, predictions, labels=unique_labels, zero_division=0, output_dict=True
    )

    metrics = {
        "accuracy": round(accuracy_score(y_test, predictions), 4),
        "precision": round(precision_score(y_test, predictions, average="macro", zero_division=0), 4),
        "recall": round(recall_score(y_test, predictions, average="macro", zero_division=0), 4),
        "f1": round(f1_score(y_test, predictions, average="macro", zero_division=0), 4),
        "samples": len(texts),
        "train_samples": len(X_train.toarray()),
        "test_samples": len(X_test.toarray()),
        "classes": unique_labels,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }

    save_model(model, vectorizer, labels, kind)
    return model, vectorizer, metrics


def _classify(text, kind):
    """Shared prediction routine for a given model kind."""
    model, vectorizer = load_model(kind)
    if model is None:
        return None, {}
    X = vectorizer.transform([_preprocess_text(text, kind)])
    probs = model.predict_proba(X)[0]
    predicted = model.classes_[probs.argmax()]
    scores = {
        cls: round(float(p) * 100, 2)
        for cls, p in zip(model.classes_, probs)
    }
    return predicted, scores


def prepare_dataset(documents):
    """Split (title + content) and labels from Document records."""
    texts = [doc.content or "" for doc in documents]
    labels = [doc.category for doc in documents]
    return texts, labels


# --- Document TYPE model (backwards-compatible public API) -----------------

def train_naive_bayes(texts, labels):
    """Train the document-type Multinomial Naive Bayes classifier (80/20 split)."""
    return _train(texts, labels, "type")


def classify_text(text):
    """Predict the document type of an unseen document."""
    return _classify(text, "type")


def save_model(model, vectorizer, labels, kind="type"):
    model_path, vec_path, label_path = _paths(kind)
    joblib.dump(model, model_path)
    joblib.dump(vectorizer, vec_path)
    with open(label_path, "w", encoding="utf-8") as f:
        json.dump(sorted(labels), f)


def load_model(kind="type"):
    model_path, vec_path, _label_path = _paths(kind)
    if not (os.path.exists(model_path) and os.path.exists(vec_path)):
        return None, None
    model = joblib.load(model_path)
    vectorizer = joblib.load(vec_path)
    return model, vectorizer


# --- Project DOMAIN model ---------------------------------------------------

def train_domain_model(texts, labels):
    """Train the project-category/domain Multinomial Naive Bayes classifier."""
    return _train(texts, labels, "domain")


def classify_domain(text):
    """Predict the project category/domain of an unseen document."""
    return _classify(text, "domain")
