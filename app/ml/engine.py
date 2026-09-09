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
import hashlib
import json
import os
import random
import re

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
from sklearn.naive_bayes import MultinomialNB

from app.ml.preprocess import preprocess, preprocess_domain
from app.models import DOCUMENT_CATEGORIES, PROJECT_CATEGORIES

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Documented, reproducible split configuration used everywhere a train/test
# assignment is made.
SPLIT_RATIO = {"train": 0.8, "test": 0.2}
SPLIT_SEED = 42
SPLIT_METHOD = "Stratified 80/20 by category (per-class allocation, random_state=42)"

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
    """Shared training routine for a given model kind (leakage-free)."""
    vectorizer, X_train, X_test, idx_train, idx_test, y_train, y_test = (
        _fit_on_train_only(texts, labels, kind)
    )

    # Type classes are roughly balanced (informative priors help); domain classes
    # are imbalanced (uniform priors avoid always predicting the majority class).
    model = MultinomialNB(alpha=1.0, fit_prior=(kind == "type"))
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    unique_labels = sorted(set(labels))
    metrics = _evaluation_metrics(
        y_test, predictions, unique_labels, len(texts), idx_train, idx_test
    )

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


def get_dataset_summary(documents):
    """Return a full summary of the labeled training dataset.

    Includes total datapoints, per-category and per-domain distributions,
    and the 80/20 stratified split sizes.
    """
    from collections import Counter

    total = len(documents)
    type_docs = [d for d in documents if d.category is not None]
    domain_docs = [d for d in documents if d.domain is not None]

    type_labels = [d.category for d in type_docs]
    domain_labels = [d.domain for d in domain_docs]

    type_dist = dict(Counter(type_labels).most_common())
    domain_dist = dict(Counter(domain_labels).most_common())

    train_ratio = 0.8
    test_ratio = 0.2

    type_indices = list(range(len(type_docs)))
    if type_docs:
        type_train_idx, type_test_idx, _, _ = _stratified_split(type_indices, type_labels)
        type_train, type_test = len(type_train_idx), len(type_test_idx)
    else:
        type_train = type_test = 0

    domain_indices = list(range(len(domain_docs)))
    if domain_docs:
        domain_train_idx, domain_test_idx, _, _ = _stratified_split(domain_indices, domain_labels)
        domain_train, domain_test = len(domain_train_idx), len(domain_test_idx)
    else:
        domain_train = domain_test = 0

    ground_truth_types = sorted(set(type_labels))
    ground_truth_domains = sorted(set(domain_labels))

    type_split_assignment = {}
    for i in type_train_idx:
        type_split_assignment[type_docs[i].id] = "TRAIN"
    for i in type_test_idx:
        type_split_assignment[type_docs[i].id] = "TEST"

    domain_split_assignment = {}
    for i in domain_train_idx:
        domain_split_assignment[domain_docs[i].id] = "TRAIN"
    for i in domain_test_idx:
        domain_split_assignment[domain_docs[i].id] = "TEST"

    def _by_class(labels, train_idx, test_idx):
        counts = {}
        for label in sorted(set(labels)):
            n_train = sum(1 for i in train_idx if labels[i] == label)
            n_test = sum(1 for i in test_idx if labels[i] == label)
            counts[label] = {"train": n_train, "test": n_test}
        return counts

    type_split_by_class = _by_class(type_labels, type_train_idx, type_test_idx)
    domain_split_by_class = _by_class(domain_labels, domain_train_idx, domain_test_idx)

    return {
        "total_datapoints": total,
        "type_datapoints": len(type_docs),
        "domain_datapoints": len(domain_docs),
        "type_distribution": type_dist,
        "domain_distribution": domain_dist,
        "ground_truth_types": ground_truth_types,
        "ground_truth_domains": ground_truth_domains,
        "type_split": {"train": type_train, "test": type_test},
        "domain_split": {"train": domain_train, "test": domain_test},
        "split_ratio": {"train": 0.8, "test": 0.2},
        "type_split_by_class": type_split_by_class,
        "domain_split_by_class": domain_split_by_class,
        "type_split_assignment": type_split_assignment,
        "domain_split_assignment": domain_split_assignment,
        "type_documents": [
            {"id": d.id, "title": d.title, "category": d.category, "domain": d.domain}
            for d in type_docs
        ],
        "domain_documents": [
            {"id": d.id, "title": d.title, "category": d.category, "domain": d.domain}
            for d in domain_docs
        ],
    }


def _label_field(kind):
    """DB column holding the ground-truth label for a classification kind."""
    return "category" if kind == "type" else "domain"


def _allowed_labels(kind):
    """Ground-truth labels accepted for a classification kind."""
    return set(DOCUMENT_CATEGORIES) if kind == "type" else set(PROJECT_CATEGORIES)


def _content_key(content):
    """Canonical content fingerprint for exact-duplicate detection."""
    return re.sub(r"\s+", " ", (content or "").strip().lower())


def validate_labeled_documents(documents, kind):
    """Validate ground-truth labels and remove duplicate documents.

    Performed BEFORE the train/test split so the split only ever sees verified,
    de-duplicated data:
      - a document must have a ground-truth label from the accepted category/
        domain list and a non-empty content body;
      - documents whose exact content (or title) repeats are dropped, keeping
        only the first occurrence, so the same document can never appear in
        both training and testing.

    Returns ``(valid_docs, summary)`` where summary records how many documents
    were scanned/accepted and how many were dropped and for what reason.
    """
    seen_content = set()
    seen_title = set()
    accepted = []
    dropped = {"missing_label": 0, "invalid_label": 0, "empty_content": 0, "duplicate": 0}

    label_field = _label_field(kind)
    allowed = _allowed_labels(kind)

    for doc in documents:
        label = (getattr(doc, label_field) or "").strip()
        title = (doc.title or "").strip()
        content = (doc.content or "").strip()

        if not label:
            dropped["missing_label"] += 1
            continue
        if label not in allowed:
            dropped["invalid_label"] += 1
            continue
        if not content:
            dropped["empty_content"] += 1
            continue

        title_key = title.lower()
        content_key = _content_key(content)
        if title_key in seen_title or content_key in seen_content:
            dropped["duplicate"] += 1
            continue

        seen_title.add(title_key)
        seen_content.add(content_key)
        accepted.append(doc)

    return accepted, {
        "kind": "document type" if kind == "type" else "project category",
        "scanned": len(documents),
        "accepted": len(accepted),
        "dropped": dropped,
    }


def _dataset_id(docs, kind):
    """Deterministic dataset identifier derived from the document ids."""
    ids = sorted(str(d.id) for d in docs)
    digest = hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:10]
    return f"CELMIS-{kind}-D{len(ids)}-{digest}"


def prepare_stratified_dataset(documents, kind):
    """Validate labels, de-duplicate, then apply the documented 80/20 split.

    Returns ``(valid_docs, meta)``. ``meta`` records everything needed to
    reproduce and verify the split: dataset identifier, split method and seed,
    per-category train/test distribution, the exact train/test document ids,
    the overlap check, and the label-validation summary.
    """
    docs, validation = validate_labeled_documents(documents, kind)

    label_field = _label_field(kind)
    labels = [getattr(d, label_field) for d in docs]
    ids = [d.id for d in docs]

    indices = list(range(len(docs)))
    idx_train, idx_test, y_train, y_test = _stratified_split(indices, labels)

    train_ids = [ids[i] for i in idx_train]
    test_ids = [ids[i] for i in idx_test]

    distribution = {}
    for label in sorted(set(labels)):
        distribution[label] = {
            "total": labels.count(label),
            "train": sum(1 for i in idx_train if labels[i] == label),
            "test": sum(1 for i in idx_test if labels[i] == label),
        }

    meta = {
        "kind": validation["kind"],
        "kind_code": kind,
        "split_method": SPLIT_METHOD,
        "split": dict(SPLIT_RATIO),
        "split_seed": SPLIT_SEED,
        "dataset_id": _dataset_id(docs, kind),
        "train_count": len(train_ids),
        "test_count": len(test_ids),
        "validation": validation,
        "distribution": distribution,
        "train_document_ids": train_ids,
        "test_document_ids": test_ids,
        "overlap_document_ids": sorted(set(train_ids) & set(test_ids)),
        "train_indices": idx_train,
        "test_indices": idx_test,
        "y_train": list(y_train),
        "y_test": list(y_test),
        "all_labels": sorted(set(labels)),
    }
    return docs, meta


def build_and_train(documents, kind):
    """Validated, leakage-free training pipeline with full reproducibility metadata.

    Order of operations:
      1. validate ground-truth labels (category/domain must be from the accepted list);
      2. remove exact-duplicate documents;
      3. stratified 80/20 split (seed 42) preserving each category's distribution;
      4. fit TF-IDF on the training split ONLY;
      5. fit Multinomial Naive Bayes; evaluate on the held-out test split.

    Returns ``(model, vectorizer, metrics, used_documents)``. ``metrics["dataset"]``
    records the total dataset size, category distribution, train/test counts, the
    split method, and dataset identifiers for reproducibility/verification.
    """
    docs, meta = prepare_stratified_dataset(documents, kind)
    if not docs:
        raise ValueError("No validated labeled documents are available to train on.")

    label_field = _label_field(kind)
    texts = [doc.content or "" for doc in docs]
    raw = [_preprocess_text(t, kind) for t in texts]

    idx_train, idx_test = meta["train_indices"], meta["test_indices"]
    y_train, y_test = meta["y_train"], meta["y_test"]

    vectorizer = _vectorizer()
    X_train = vectorizer.fit_transform([raw[i] for i in idx_train])
    X_test = vectorizer.transform([raw[i] for i in idx_test])

    model = MultinomialNB(alpha=1.0, fit_prior=(kind == "type"))
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    metrics = _evaluation_metrics(y_test, predictions, meta["all_labels"], len(docs), idx_train, idx_test)

    metrics["split_method"] = meta["split_method"]
    metrics["split_seed"] = meta["split_seed"]
    metrics["dataset_id"] = meta["dataset_id"]
    metrics["dataset"] = {
        "kind": meta["kind"],
        "kind_code": kind,
        "split_method": meta["split_method"],
        "split": meta["split"],
        "split_seed": meta["split_seed"],
        "dataset_id": meta["dataset_id"],
        "train_count": meta["train_count"],
        "test_count": meta["test_count"],
        "validation": meta["validation"],
        "distribution": meta["distribution"],
        "train_document_ids": meta["train_document_ids"],
        "test_document_ids": meta["test_document_ids"],
        "overlap_document_ids": meta["overlap_document_ids"],
    }

    save_model(model, vectorizer, meta["all_labels"], kind)
    return model, vectorizer, metrics, docs


def _evaluation_metrics(y_test, predictions, unique_labels, total_samples, idx_train, idx_test):
    """Build the evaluation metric dict from a held-out test split.

    The accuracy, per-class correct/incorrect counts, confusion matrix, and
    classification report are all computed ONLY from the held-out test
    documents. Nothing in this function touches training data, so the reported
    accuracy cannot be inflated by data leakage.
    """
    cm = confusion_matrix(y_test, predictions, labels=unique_labels)
    report = classification_report(
        y_test, predictions, labels=unique_labels, zero_division=0, output_dict=True
    )

    correct = int(sum(1 for a, b in zip(y_test, predictions) if a == b))
    incorrect = len(y_test) - correct

    per_class = {}
    for label in unique_labels:
        idx = [i for i, v in enumerate(y_test) if v == label]
        n = len(idx)
        c = int(sum(1 for i in idx if predictions[i] == label))
        per_class[label] = {"total": n, "correct": c, "incorrect": n - c}

    return {
        "accuracy": round(correct / len(y_test), 4) if y_test else 0.0,
        "accuracy_detail": {
            "correct": correct,
            "incorrect": incorrect,
            "total_tested": len(y_test),
            "computation": f"{correct} / {len(y_test)}",
            "percent": round(correct / len(y_test) * 100, 2) if y_test else 0.0,
        },
        "per_class_test": per_class,
        "precision": round(precision_score(y_test, predictions, average="macro", zero_division=0), 4),
        "recall": round(recall_score(y_test, predictions, average="macro", zero_division=0), 4),
        "f1": round(f1_score(y_test, predictions, average="macro", zero_division=0), 4),
        "samples": total_samples,
        "train_samples": len(idx_train),
        "test_samples": len(idx_test),
        "classes": unique_labels,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "train_indices": idx_train,
        "test_indices": idx_test,
        "y_test": list(y_test),
        "predictions": list(predictions),
    }


def _fit_on_train_only(texts, labels, kind):
    """Stratified split BEFORE any fitting, then fit TF-IDF on the training set.

    Doing the split first and fitting the vectorizer exclusively on the 80%
    training documents guarantees the test documents never influence the TF-IDF
    vocabulary, idf weights, or the classifier — eliminating data leakage.
    """
    indices = list(range(len(texts)))
    idx_train, idx_test, y_train, y_test = _stratified_split(indices, labels)

    raw = [_preprocess_text(t, kind) for t in texts]
    vectorizer = _vectorizer()
    X_train = vectorizer.fit_transform([raw[i] for i in idx_train])
    X_test = vectorizer.transform([raw[i] for i in idx_test])

    return vectorizer, X_train, X_test, idx_train, idx_test, y_train, y_test


def train_naive_bayes_detailed(texts, labels):
    """Train the document-type classifier and return full evaluation details.

    The 80/20 stratified split is performed first and the TF-IDF vectorizer is
    fitted ONLY on the training split, so evaluation is on truly unseen test
    data (no data leakage). Returns train/test indices for verification.
    """
    vectorizer, X_train, X_test, idx_train, idx_test, y_train, y_test = (
        _fit_on_train_only(texts, labels, "type")
    )

    model = MultinomialNB(alpha=1.0, fit_prior=True)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    unique_labels = sorted(set(labels))
    metrics = _evaluation_metrics(
        y_test, predictions, unique_labels, len(texts), idx_train, idx_test
    )

    save_model(model, vectorizer, sorted(set(labels)), "type")
    return model, vectorizer, metrics


def train_domain_model_detailed(texts, labels):
    """Train the domain classifier and return full evaluation details.

    Same leakage-free procedure as train_naive_bayes_detailed: split first,
    then fit TF-IDF on the training split only.
    """
    vectorizer, X_train, X_test, idx_train, idx_test, y_train, y_test = (
        _fit_on_train_only(texts, labels, "domain")
    )

    model = MultinomialNB(alpha=1.0, fit_prior=False)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    unique_labels = sorted(set(labels))
    metrics = _evaluation_metrics(
        y_test, predictions, unique_labels, len(texts), idx_train, idx_test
    )

    save_model(model, vectorizer, sorted(set(labels)), "domain")
    return model, vectorizer, metrics


def _stratified_split(indices, labels):
    """Return train/test index lists using the documented stratified 80/20 split.

    Each label/category is allocated to train and test separately so the class
    distribution of the whole dataset is preserved in both splits. The allocation
    is deterministic (``random.Random(SPLIT_SEED)``), making every split
    reproducible. Every category with at least two documents contributes at
    least one test document; a category with a single document is kept in the
    training split (it cannot be meaningfully held out).
    """
    from collections import defaultdict

    by_label = defaultdict(list)
    for i, label in zip(indices, labels):
        by_label[label].append(i)

    rng = random.Random(SPLIT_SEED)

    train_idx = []
    test_idx = []
    for items in by_label.values():
        rng.shuffle(items)
        n = len(items)
        if n == 1:
            n_test = 0
        else:
            n_test = min(max(1, round(n * SPLIT_RATIO["test"])), n - 1)
        test_idx.extend(items[:n_test])
        train_idx.extend(items[n_test:])

    y_train = [labels[i] for i in train_idx]
    y_test = [labels[i] for i in test_idx]

    return train_idx, test_idx, y_train, y_test


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


# --- Content objective extraction --------------------------------------------

_OBJECTIVE_SIGNALS = [
    "objective", "purpose", "pursuant", "WHEREAS", "witnesseth", "whereas",
    "agree", "agrees", "undertake", "establish", "implement", "provide",
    "deliver", "initiate", "collaborat", "partnership", "assist", "commit",
    "intends to", "aims to", "is to", "jointly", "community", "program",
    "shall", "services", "train", "render", "cooperation",
]


def _split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return [s.strip() for s in parts if len(s.split()) > 4]


def extract_objective(content, max_chars=260):
    """Return a short extractive objective of the document content.

    Sentence-frequency heuristic: sentences that carry action/purpose signal
    words are ranked, and the best one (plus a strong runner-up that fits) is
    returned. Falls back to the raw opening text when no sentences are found.
    """
    sents = _split_sentences(content)
    if not sents:
        return (content or "").strip()[:max_chars]

    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        score = sum(1 for w in _OBJECTIVE_SIGNALS if w.lower() in low)
        if any(v in low for v in ("agree", "shall", "aims to", "is to", "shall provide", "jointly")):
            score += 2
        scored.append((score, i, s))

    scored.sort(key=lambda t: (-t[0], t[1]))
    result = scored[0][2]
    for _, _, other in scored[1:]:
        if other != result and len(result) + len(other) <= max_chars:
            result += " " + other
            break

    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0] + "…"
    return result
