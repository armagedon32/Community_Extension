"""Bulk import training/classification documents from a CSV file.

Usage:
    python import_documents.py [path/to/file.csv]

The CSV must have columns: title,category,domain,content
  - category: document type (e.g. Project Proposal, Activity Design, MOA...)
  - domain:   project category (e.g. Education, Livelihood, Governance, Environment...)

How to use:
  - TRAINING:  fill in category AND domain. These examples teach the model.
  - TEST:      leave category and domain EMPTY. The AI auto-classifies them
               from the content (using the last trained models).

Lines starting with '#' are treated as comments and skipped.
"""
import csv
import sys

from app import create_app, db
from app.models import DOCUMENT_CATEGORIES, PROJECT_CATEGORIES, Document, User

DEFAULT_FILE = "templates/training_documents.csv"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()

        from app.ml.engine import classify_text, classify_domain

        added = 0
        skipped = 0
        errors = []
        predictions = []
        with open(path, "r", encoding="utf-8-sig") as f:
            rows = [line for line in f if not line.lstrip().startswith("#")]
            reader = csv.DictReader(rows)
            for row_num, row in enumerate(reader, start=1):
                if (row.get("title") or "").strip().startswith("#"):
                    continue
                title = (row.get("title") or "").strip()
                category = (row.get("category") or "").strip()
                domain = (row.get("domain") or "").strip()
                content = (row.get("content") or "").strip()

                if not title or not content:
                    skipped += 1
                    errors.append(f"Row {row_num}: missing title or content")
                    continue

                if category and category not in DOCUMENT_CATEGORIES:
                    skipped += 1
                    errors.append(
                        f"Row {row_num}: invalid category '{category}'. "
                        f"Use one of: {', '.join(DOCUMENT_CATEGORIES)}"
                    )
                    continue

                if domain and domain not in PROJECT_CATEGORIES:
                    skipped += 1
                    errors.append(
                        f"Row {row_num}: invalid domain '{domain}'. "
                        f"Use one of: {', '.join(PROJECT_CATEGORIES)}"
                    )
                    continue

                doc = Document(
                    title=title,
                    category=category or None,
                    domain=domain or None,
                    content=content,
                    is_training=True,
                    uploaded_by=admin.id if admin else None,
                )
                db.session.add(doc)
                db.session.flush()
                added += 1

                # Auto-classify rows that have NO labels
                if not category and not domain:
                    pred_type, _ = classify_text(content)
                    pred_domain, _ = classify_domain(content)
                    if pred_type:
                        doc.predicted_category = pred_type
                    if pred_domain:
                        doc.predicted_domain = pred_domain
                    predictions.append((title, pred_type, pred_domain))

        db.session.commit()
        type_total = Document.query.filter(Document.is_training.is_(True), Document.category.isnot(None)).count()
        domain_total = Document.query.filter(Document.is_training.is_(True), Document.domain.isnot(None)).count()
        print(f"Imported: {added} document(s)")
        print(f"Skipped:  {skipped} row(s)")
        print(f"Labeled by type in DB now:   {type_total}")
        print(f"Labeled by domain in DB now: {domain_total}")
        for e in errors:
            print("  -", e)

        if predictions:
            print()
            print("Auto-classified (from content, no label filled):")
            for title, pt, pd in predictions:
                print(f"  {title[:40]:42s} Type = {str(pt):22s} Domain = {str(pd)}")

        print("\nNote: to TRAIN the model, use a CSV with labels filled and click 'Train Naive Bayes'.")


if __name__ == "__main__":
    main()
