import json
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.models import DOCUMENT_CATEGORIES, PROJECT_CATEGORIES, Document, MLModel

ml_bp = Blueprint("ml", __name__)

_ALLOWED_EXT = {"txt", "pdf", "doc", "docx"}


def _doc_folder():
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "documents")
    return folder


def _save_upload(file):
    os.makedirs(_doc_folder(), exist_ok=True)
    filename = secure_filename(file.filename) or "document.txt"
    file.save(os.path.join(_doc_folder(), filename))
    return filename


def _read_uploaded_text(filename):
    """Extract readable text from an uploaded document.

    Supports plain text (.txt), PDF (.pdf) and Word (.docx). ``.doc`` files
    have no pure-Python text extractor, so they fall back to a best-effort
    raw read that is usually not useful for classification.
    """
    path = os.path.join(_doc_folder(), os.path.basename(filename))
    if not os.path.exists(path):
        return ""

    ext = (os.path.splitext(filename)[1] or "").lower()
    try:
        if ext == ".pdf":
            return _extract_pdf(path)
        if ext == ".docx":
            return _extract_docx(path)
        if ext == ".doc":
            with open(path, "rb") as f:
                return f.read().decode("utf-8", errors="ignore")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _extract_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def _extract_docx(path):
    from docx import Document as DocxDocument
    doc = DocxDocument(path)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _delete_doc_file(filename):
    path = os.path.join(_doc_folder(), os.path.basename(filename))
    if os.path.exists(path):
        os.remove(path)


@ml_bp.route("/ml/documents")
@login_required
def list_documents():
    _scan_unclassified()

    from sqlalchemy import or_

    type_filter = (request.args.get("type") or "").strip()
    domain_filter = (request.args.get("domain") or "").strip()

    query = Document.query
    if type_filter:
        query = query.filter(
            or_(Document.category == type_filter, Document.predicted_category == type_filter)
        )
    if domain_filter:
        query = query.filter(
            or_(Document.domain == domain_filter, Document.predicted_domain == domain_filter)
        )

    documents = query.order_by(Document.created_at.desc()).all()

    from app.ml.engine import extract_objective
    objectives = {
        doc.id: extract_objective(doc.content) for doc in documents if doc.content
    }

    return render_template(
        "ml/documents.html",
        documents=documents,
        objectives=objectives,
        type_filter=type_filter,
        domain_filter=domain_filter,
        DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
    )


def _predict_missing(doc):
    """Predict any field that a document is still missing.

    A document may be labeled for its *document type* but have no *project
    category* (or vice versa). This fills the empty one without overwriting
    the existing label.
    """
    from app.ml.engine import classify_text, classify_domain

    if not doc.content:
        return
    _ensure_models()
    if doc.category is None and not doc.predicted_category:
        try:
            pred, _ = classify_text(doc.content)
            if pred:
                doc.predicted_category = pred
        except Exception:
            pass
    if doc.domain is None and not doc.predicted_domain:
        try:
            p_dom, _ = classify_domain(doc.content)
            if p_dom:
                doc.predicted_domain = p_dom
        except Exception:
            pass


def _scan_unclassified():
    """Auto-scan so every document shows a project category on page load.

    Re-reads the content from the stored file for any document whose content
    is empty (e.g. uploaded before PDF text extraction existed), then predicts
    the *project category* (and type) from that scanned content.
    """
    docs = (
        Document.query
        .order_by(Document.created_at.desc())
        .all()
    )
    for doc in docs:
        if not doc.content and doc.filename:
            doc.content = _read_uploaded_text(doc.filename)
        if not (doc.domain or doc.predicted_domain) or not (doc.category or doc.predicted_category):
            _predict_missing(doc)
    db.session.commit()


@ml_bp.route("/ml/documents/new", methods=["GET", "POST"])
@login_required
def add_document():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        domain = request.form.get("domain", "").strip()
        content = request.form.get("content", "").strip()
        is_training = True if request.form.get("is_training") else False
        filename = None

        file = request.files.get("file")
        if file and file.filename:
            filename = _save_upload(file)
            if not content:
                content = _read_uploaded_text(filename)

        if not title or not content:
            flash("Document title and content are required.", "danger")
            return render_template(
                "ml/document_form.html",
                document=None,
                DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
                PROJECT_CATEGORIES=PROJECT_CATEGORIES,
            )

        doc = Document(
            title=title,
            category=category if category else None,
            domain=domain if domain else None,
            content=content,
            filename=filename,
            is_training=is_training,
            uploaded_by=current_user.id,
        )
        db.session.add(doc)
        db.session.commit()

        _predict_missing(doc)
        db.session.commit()

        if is_training and (category or domain):
            flash("Labeled document added. Retrain the model to include it.", "success")
        elif doc.predicted_category or doc.predicted_domain:
            parts = [p for p in (doc.predicted_category, doc.predicted_domain) if p]
            flash(f"Document scanned. Project category detected: {parts[-1]}", "success")
        else:
            flash("Document saved. Could not auto-detect a category for this content yet.", "warning")
        return redirect(url_for("ml.list_documents"))

    return render_template(
        "ml/document_form.html",
        document=None,
        DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
    )


@ml_bp.route("/ml/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = db.get_or_404(Document, doc_id)
    if doc.filename:
        _delete_doc_file(doc.filename)
    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "info")
    return redirect(url_for("ml.list_documents"))


def _next_version(name):
    """Increment the model version based on existing MLModel runs."""
    existing = MLModel.query.filter(MLModel.name == name).count()
    return f"v{existing + 1}"


def _attach_test_predictions(metrics, docs):
    """Attach per-test-sample truth vs prediction for verification.

    The stored metrics already contain the held-out test indices and the
    actual predictions; this pairs each test document with its true label,
    predicted label, and whether the prediction was correct, so the numbers
    reported for Research Question No. 4 are fully verifiable.
    """
    titles = [d.title or "" for d in docs]
    y_test = metrics.get("y_test") or []
    preds = metrics.get("predictions") or []
    idx = metrics.get("test_indices") or []
    metrics["test_predictions"] = [
        {
            "title": titles[i] if 0 <= i < len(titles) else f"sample-{i}",
            "actual": y_test[k],
            "predicted": preds[k],
            "correct": y_test[k] == preds[k],
        }
        for k, i in enumerate(idx)
    ]


def _record_model_run(name, metrics, dataset_summary=None, version=None):
    """Record a trained (not yet activated) model run."""
    dist = None
    if dataset_summary:
        if "Project Category" in name:
            dist = json.dumps(dataset_summary.get("domain_distribution") or {})
        else:
            dist = json.dumps(dataset_summary.get("type_distribution") or {})
    model_run = MLModel(
        name=name,
        model_type="Multinomial Naive Bayes",
        status="Trained",
        accuracy=metrics.get("accuracy"),
        precision=metrics.get("precision"),
        recall=metrics.get("recall"),
        f1=metrics.get("f1"),
        samples=metrics.get("samples", 0),
        classes=", ".join(metrics.get("classes") or []),
        metrics_json=json.dumps(metrics, default=str),
        dataset_size=metrics.get("samples", 0),
        class_distribution=dist,
        model_version=version,
        train_samples=metrics.get("train_samples"),
        test_samples=metrics.get("test_samples"),
        split_ratio="80/20",
    )
    db.session.add(model_run)
    db.session.commit()
    return model_run


@ml_bp.route("/ml/train", methods=["POST"])
@login_required
def train_model():
    """Step 1 of the train->evaluate->activate workflow: TRAIN the models.

    Trains both classifiers on the current labeled dataset but does NOT
    activate them — the researcher reviews the evaluation first.
    """
    import time
    from app.ml import engine

    type_docs = (
        Document.query
        .filter(Document.is_training.is_(True), Document.category.isnot(None))
        .all()
    )
    if len(type_docs) < 3:
        flash("At least 3 labeled training documents are required.", "danger")
        return redirect(url_for("ml.dashboard"))

    summary = engine.get_dataset_summary(
        Document.query.filter(Document.is_training.is_(True)).all()
    )

    # --- Document type model ---
    texts = [doc.content or "" for doc in type_docs]
    labels = [doc.category for doc in type_docs]
    started = time.time()
    model, vectorizer, metrics = engine.train_naive_bayes_detailed(texts, labels)
    duration = round(time.time() - started, 2)
    metrics["training_duration"] = duration
    _attach_test_predictions(metrics, type_docs)
    engine.save_model(model, vectorizer, metrics["classes"], "type")

    _record_model_run(
        "Multinomial Naive Bayes - Document Type",
        metrics,
        dataset_summary=summary,
        version=_next_version("Multinomial Naive Bayes - Document Type"),
    )

    # --- Project category/domain model ---
    domain_docs = (
        Document.query
        .filter(Document.is_training.is_(True), Document.domain.isnot(None))
        .all()
    )
    d_metrics = None
    if len(domain_docs) >= 3:
        domain_texts = [doc.content or "" for doc in domain_docs]
        domain_labels = [doc.domain for doc in domain_docs]
        started = time.time()
        d_model, d_vec, d_metrics = engine.train_domain_model_detailed(domain_texts, domain_labels)
        d_metrics["training_duration"] = round(time.time() - started, 2)
        _attach_test_predictions(d_metrics, domain_docs)
        _record_model_run(
            "Multinomial Naive Bayes - Project Category",
            d_metrics,
            dataset_summary=summary,
            version=_next_version("Multinomial Naive Bayes - Project Category"),
        )

    verdict = []
    for nm, m in (("Document Type", metrics), ("Project Category", d_metrics)):
        if m:
            verdict.append(f"{nm}: Accuracy {m['accuracy']:.0%}, F1 {m['f1']:.0%}")

    flash(
        "Models trained and evaluated on the held-out 20% test set. Review the "
        "results below, then click ACTIVATE to make the models live. "
        + " | ".join(verdict),
        "success",
    )
    from app.routes.notifications import notify
    notify(
        f"Models trained and evaluated (not yet activated): {' | '.join(verdict)}. Review then activate.",
        category="info",
        link=url_for("ml.dashboard"),
    )
    return redirect(url_for("ml.dashboard"))


@ml_bp.route("/ml/activate/<int:model_id>", methods=["POST"])
@login_required
def activate_model(model_id):
    """Step 3 of the workflow: ACTIVATE a single evaluated model."""
    from datetime import datetime

    model_run = db.get_or_404(MLModel, model_id)
    if model_run.status != "Trained":
        flash("This model is not in the 'Trained' state and cannot be activated.", "warning")
        return redirect(url_for("ml.dashboard"))

    # Archive any other ACTIVE model of the same family (type or domain), not
    # the sibling classifier.
    MLModel.query.filter(
        MLModel.name == model_run.name
    ).filter(MLModel.id != model_run.id).filter(MLModel.status.like("Active%")).update({"status": "Archived"})

    model_run.status = "Active"
    model_run.activated_at = datetime.utcnow()
    db.session.commit()

    flash(f"Model '{model_run.name}' ({model_run.model_version}) is now ACTIVE.", "success")
    from app.routes.notifications import notify
    notify(
        f"Model '{model_run.name}' ({model_run.model_version}) activated.",
        category="success",
        link=url_for("ml.dashboard"),
    )
    return redirect(url_for("ml.dashboard"))


@ml_bp.route("/ml/deactivate/<int:model_id>", methods=["POST"])
@login_required
def deactivate_model(model_id):
    """Set a model back to 'Trained' (deactivate) without deleting its record."""
    model_run = db.get_or_404(MLModel, model_id)
    model_run.status = "Trained"
    model_run.activated_at = None
    db.session.commit()
    flash(f"Model '{model_run.name}' deactivated.", "info")
    return redirect(url_for("ml.dashboard"))


@ml_bp.route("/ml/classify/<int:doc_id>", methods=["POST"])
@login_required
def classify_document(doc_id):
    doc = db.get_or_404(Document, doc_id)
    _classify_and_store(doc)
    return redirect(url_for("ml.list_documents"))


@ml_bp.route("/ml/documents/<int:doc_id>/print")
@login_required
def print_document(doc_id):
    from datetime import datetime

    doc = db.get_or_404(Document, doc_id)
    return render_template(
        "ml/document_print.html",
        doc=doc,
        generated_at=datetime.now().strftime("%B %d, %Y %I:%M %p"),
    )


def _ensure_models():
    """Train any missing classifier on-demand so classification always works.

    Unlike the explicit Train step (which produces a full evaluation), this is a
    fallback that only fires when NO trained model artifact exists, e.g. on a
    fresh deployment after the bootstrap has populated labeled data. It records
    the run in the MLModel registry for transparency.

    Returns True if both requested classifiers (type + domain) are ready.
    """
    import time
    from app.ml import engine

    trained = {}
    docs = (
        Document.query
        .filter(Document.is_training.is_(True), Document.category.isnot(None))
        .all()
    )
    if engine.load_model("type")[0] is None and len(docs) >= 3:
        strong = MLModel.query.filter(MLModel.name == "Multinomial Naive Bayes - Document Type").count()
        if strong == 0:
            summary = engine.get_dataset_summary(
                Document.query.filter(Document.is_training.is_(True)).all()
            )
            started = time.time()
            model, vectorizer, metrics = engine.train_naive_bayes_detailed(
                [d.content or "" for d in docs],
                [d.category for d in docs],
            )
            metrics["training_duration"] = round(time.time() - started, 2)
            engine.save_model(model, vectorizer, metrics["classes"], "type")
            _record_model_run(
                "Multinomial Naive Bayes - Document Type",
                metrics,
                dataset_summary=summary,
                version="v1",
            )
            trained["type"] = True

    domain_docs = (
        Document.query
        .filter(Document.is_training.is_(True), Document.domain.isnot(None))
        .all()
    )
    if engine.load_model("domain")[0] is None and len(domain_docs) >= 3:
        strong_d = MLModel.query.filter(MLModel.name == "Multinomial Naive Bayes - Project Category").count()
        if strong_d == 0:
            summary = engine.get_dataset_summary(
                Document.query.filter(Document.is_training.is_(True)).all()
            )
            started = time.time()
            d_model, d_vec, d_metrics = engine.train_domain_model_detailed(
                [d.content or "" for d in domain_docs],
                [d.domain for d in domain_docs],
            )
            d_metrics["training_duration"] = round(time.time() - started, 2)
            _record_model_run(
                "Multinomial Naive Bayes - Project Category",
                d_metrics,
                dataset_summary=summary,
                version="v1",
            )
            trained["domain"] = True

    return trained


def _classify_and_store(doc):
    from app.ml.engine import classify_text, classify_domain

    _ensure_models()

    predicted, scores = classify_text(doc.content)
    if predicted:
        doc.predicted_category = predicted
    predicted_domain, _d_scores = classify_domain(doc.content)
    if predicted_domain:
        doc.predicted_domain = predicted_domain
    db.session.commit()

    parts = [p for p in (predicted, predicted_domain) if p]
    if parts:
        flash(f"Document classified as: {' / '.join(parts)}", "success")
        from app.routes.notifications import notify
        notify(
            f"Document '{doc.title}' classified as {' / '.join(parts)}.",
            category="success",
            link=url_for("ml.list_documents"),
        )
    else:
        flash("Unable to classify this document (not enough training data yet).", "warning")


def _metrics_view(model):
    """Parse a model run's stored metrics into a display-ready dict.

    Returns the quantitative evaluation results (accuracy, precision, recall,
    F1, confusion matrix, per-class report, accuracy computation, and the
    per-sample test predictions) required for Research Question No. 4.
    """
    if model is None or not model.metrics_json:
        return None
    try:
        m = json.loads(model.metrics_json)
        report = m.get("classification_report") or {}
        return {
            "accuracy": m.get("accuracy"),
            "precision": m.get("precision"),
            "recall": m.get("recall"),
            "f1": m.get("f1"),
            "confusion_matrix": m.get("confusion_matrix"),
            "classes": m.get("classes"),
            "test_samples": m.get("test_samples"),
            "train_samples": m.get("train_samples"),
            "accuracy_detail": m.get("accuracy_detail"),
            "per_class_test": m.get("per_class_test"),
            "classification_report": report,
            "test_predictions": m.get("test_predictions"),
        }
    except Exception:
        return None


@ml_bp.route("/ml/model/<int:model_id>")
@login_required
def model_detail(model_id):
    """Full, print-able quantitative evaluation of a single model run.

    Displays the actual evaluation results required by Research Question
    No. 4 (accuracy, precision, recall, F1-score, confusion matrix, and the
    number of test samples) computed automatically from the held-out test
    predictions, together with the per-class report and the test samples
    themselves for verification and documentation.
    """
    from datetime import datetime

    model_run = db.get_or_404(MLModel, model_id)
    view = _metrics_view(model_run)
    return render_template(
        "ml/model_detail.html",
        model=model_run,
        chart=view,
        implied_by="Evaluation computed automatically from the actual "
                   "predictions on the held-out 20% testing dataset.",
        generated_at=datetime.now().strftime("%B %d, %Y %I:%M %p"),
    )


@ml_bp.route("/ml")
@login_required
def dashboard():
    from app.ml import engine

    models = MLModel.query.order_by(MLModel.created_at.desc()).all()
    labeled_count = Document.query.filter(Document.is_training.is_(True), Document.category.isnot(None)).count()
    domain_count = Document.query.filter(Document.is_training.is_(True), Document.domain.isnot(None)).count()
    doc_count = Document.query.count()

    training_docs = Document.query.filter(Document.is_training.is_(True)).all()
    dataset_summary = engine.get_dataset_summary(training_docs) if training_docs else None

    viewer_documents = []
    if dataset_summary:
        seen = set()
        type_split = dataset_summary.get("type_split_assignment") or {}
        domain_split = dataset_summary.get("domain_split_assignment") or {}
        for d in dataset_summary.get("type_documents", []) + dataset_summary.get("domain_documents", []):
            doc_id = d["id"]
            if doc_id not in seen:
                seen.add(doc_id)
                d["type_split"] = type_split.get(doc_id)
                d["domain_split"] = domain_split.get(doc_id)
                viewer_documents.append(d)

    type_model = next((m for m in models if "Document Type" in m.name and m.status != "Archived"), None)
    if type_model is None:
        type_model = next((m for m in models if "Document Type" in m.name), None)
    domain_model = next((m for m in models if "Project Category" in m.name and m.status != "Archived"), None)
    if domain_model is None:
        domain_model = next((m for m in models if "Project Category" in m.name), None)

    return render_template(
        "ml/index.html",
        models=models,
        latest=type_model,
        latest_domain=domain_model,
        latest_any_type=next((m for m in models if "Document Type" in m.name), None),
        latest_any_domain=next((m for m in models if "Project Category" in m.name), None),
        chart=_metrics_view(type_model),
        chart_domain=_metrics_view(domain_model),
        labeled=labeled_count,
        domain_count=domain_count,
        doc_count=doc_count,
        dataset_summary=dataset_summary,
        viewer_documents=viewer_documents,
        DOCUMENT_CATEGORIES=DOCUMENT_CATEGORIES,
        PROJECT_CATEGORIES=PROJECT_CATEGORIES,
    )