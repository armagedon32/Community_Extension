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
    """Seed an empty database on first boot.

    Model training is NOT performed here. Training is an explicit, transparent
    researcher action: Train Model -> Evaluate Model -> Activate Model. A safe
    fallback in ``routes/ml._ensure_models`` creates a recorded model only when
    no artifact exists and classification is actually requested.
    """
    from app.models import User

    if User.query.first() is None:
        from seed import run_seed
        run_seed(reset=False, app=app)
        print("Bootstrap: database seeded.")
