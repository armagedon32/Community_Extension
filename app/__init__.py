import json
from datetime import datetime

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now().year}

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.projects import projects_bp
    from app.routes.beneficiaries import beneficiaries_bp
    from app.routes.partners import partners_bp
    from app.routes.activities import activities_bp
    from app.routes.moas import moas_bp
    from app.routes.mous import mous_bp
    from app.routes.reports import reports_bp
    from app.routes.ml import ml_bp
    from app.routes.finance import finance_bp
    from app.routes.surveys import surveys_bp
    from app.routes.sentiment import sentiment_bp
    from app.routes.notifications import notifications_bp
    from app.routes.decision import decision_bp
    from app.routes.predictive import predictive_bp
    from app.routes.compliance import compliance_bp
    from app.routes.outcomes import outcomes_bp
    from app.routes.efficiency import efficiency_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(beneficiaries_bp)
    app.register_blueprint(partners_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(moas_bp)
    app.register_blueprint(mous_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(surveys_bp)
    app.register_blueprint(sentiment_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(decision_bp)
    app.register_blueprint(predictive_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(outcomes_bp)
    app.register_blueprint(efficiency_bp)

    with app.app_context():
        db.create_all()
        _ensure_schema(app)
        _bootstrap(app)

    return app


def _ensure_schema(app):
    """Lightweight additive migration for new MLModel columns.

    Works for any SQLAlchemy dialect (SQLite, PostgreSQL, MySQL, ...).
    Adds the new columns if they do not already exist, so existing databases
    keep working after deployment without a full migration tool.
    """
    from sqlalchemy import inspect, text

    new_cols = {
        "dataset_size": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "class_distribution": ("TEXT", "TEXT"),
        "model_version": ("VARCHAR(20)", "VARCHAR(20)"),
        "train_samples": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "test_samples": ("INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
        "split_ratio": ("VARCHAR(20) DEFAULT '80/20'", "VARCHAR(20) DEFAULT '80/20'"),
        "split_method": ("VARCHAR(120)", "VARCHAR(120)"),
        "dataset_id": ("VARCHAR(80)", "VARCHAR(80)"),
        "activated_at": ("DATETIME", "TIMESTAMP"),
        "training_duration": ("FLOAT", "FLOAT"),
    }
    dialect = db.engine.dialect.name

    try:
        existing = {c["name"] for c in inspect(db.engine).get_columns("ml_models")}
    except Exception:
        return

    for col, (generic_ddl, pg_ddl) in new_cols.items():
        if col in existing:
            continue
        if dialect == "postgresql":
            stmt = f"ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS {col} {pg_ddl}"
        else:
            stmt = f"ALTER TABLE ml_models ADD COLUMN {col} {generic_ddl}"
        with db.engine.begin() as conn:
            conn.execute(text(stmt))

    # Financial transaction approval workflow columns
    finance_cols = {
        "verifier_id": ("INTEGER", "INTEGER"),
        "verified_at": ("DATETIME", "TIMESTAMP"),
        "approver_id": ("INTEGER", "INTEGER"),
        "approved_at": ("DATETIME", "TIMESTAMP"),
        "rejected_by": ("INTEGER", "INTEGER"),
        "rejected_at": ("DATETIME", "TIMESTAMP"),
        "rejection_reason": ("TEXT", "TEXT"),
    }
    try:
        existing = {c["name"] for c in inspect(db.engine).get_columns("financial_transactions")}
    except Exception:
        return

    for col, (generic_ddl, pg_ddl) in finance_cols.items():
        if col in existing:
            continue
        if dialect == "postgresql":
            stmt = f"ALTER TABLE financial_transactions ADD COLUMN IF NOT EXISTS {col} {pg_ddl}"
        else:
            stmt = f"ALTER TABLE financial_transactions ADD COLUMN {col} {generic_ddl}"
        with db.engine.begin() as conn:
            conn.execute(text(stmt))

    # Data migration: legacy statuses -> approval workflow statuses
    with db.engine.begin() as conn:
        conn.execute(text(
            "UPDATE financial_transactions SET status = 'Approved', "
            "approver_id = recorded_by, approved_at = created_at "
            "WHERE status = 'Active'"
        ))
        conn.execute(text(
            "UPDATE financial_transactions SET status = 'Rejected', "
            "rejected_by = recorded_by, rejected_at = created_at "
            "WHERE status = 'Inactive'"
        ))


def _bootstrap(app):
    """Seed an empty database on first boot and keep ML classes up to date.

    Training is normally an explicit researcher action. The one exception is a
    schema-level class expansion: when new document types/categories are added,
    the idempotent top-up supplies their training documents and retrains the
    affected classifier once so the evaluation tables show every class.
    """
    from app.models import User

    if User.query.first() is None:
        from seed import run_seed
        run_seed(reset=False, app=app)
        print("Bootstrap: database seeded.")

    from seed import ensure_training_classes
    added = ensure_training_classes(app=app)
    if added:
        print(f"Bootstrap: added {added} training documents for new classes.")
        _retrain_incomplete_models()


def _retrain_incomplete_models():
    """Retrain once when a model's latest run has fewer classes than configured.

    Guarded by the class count, so it only fires after a new class is introduced
    and never re-trains on ordinary restarts.
    """
    from app.ml import engine
    from app.models import (
        Document, MLModel, DOCUMENT_CATEGORIES, PROJECT_CATEGORIES,
    )
    from app.routes.ml import _attach_test_predictions, _next_version, _record_model_run

    specs = (
        ("type", "Multinomial Naive Bayes - Document Type",
         Document.category, DOCUMENT_CATEGORIES),
        ("domain", "Multinomial Naive Bayes - Project Category",
         Document.domain, PROJECT_CATEGORIES),
    )
    for kind, name, field, configured in specs:
        latest = (MLModel.query.filter(MLModel.name == name)
                  .order_by(MLModel.id.desc()).first())
        classes = []
        if latest:
            try:
                classes = json.loads(latest.metrics_json or "{}").get("classes") or []
            except (ValueError, TypeError):
                classes = []
        if len(classes) >= len(configured):
            continue

        docs = Document.query.filter(
            Document.is_training.is_(True), field.isnot(None)
        ).all()
        if len(docs) < 3:
            continue
        model, vectorizer, metrics, used_docs = engine.build_and_train(docs, kind)
        _attach_test_predictions(metrics, used_docs)
        engine.save_model(model, vectorizer, metrics["classes"], kind)
        _record_model_run(name, metrics, version=_next_version(name))
        print(f"Bootstrap: retrained {name} with {len(metrics['classes'])} classes.")
