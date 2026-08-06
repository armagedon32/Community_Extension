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
    from app.routes.reports import reports_bp
    from app.routes.ml import ml_bp
    from app.routes.evaluations import evals_bp
    from app.routes.finance import finance_bp
    from app.routes.surveys import surveys_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(beneficiaries_bp)
    app.register_blueprint(partners_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(moas_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(evals_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(surveys_bp)

    with app.app_context():
        db.create_all()
        _bootstrap(app)

    return app


def _bootstrap(app):
    """Seed an empty database and warm the ML models on first boot.

    Idempotent: seeding only runs when no users exist, and models are only
    trained once the persisted artifacts are missing.
    """
    from app.models import User

    if User.query.first() is None:
        from seed import run_seed
        run_seed(reset=False, app=app)
        print("Bootstrap: database seeded.")

    try:
        from app.ml import engine
        from app.models import Document

        if engine.load_model("type")[0] is None:
            docs = (
                Document.query
                .filter(Document.is_training.is_(True), Document.category.isnot(None))
                .all()
            )
            if len(docs) >= 3:
                texts = [d.content or "" for d in docs]
                labels = [d.category for d in docs]
                model, vectorizer, metrics = engine.train_naive_bayes(texts, labels)
                engine.save_model(model, vectorizer, metrics["classes"], "type")
            domain_docs = (
                Document.query
                .filter(Document.is_training.is_(True), Document.domain.isnot(None))
                .all()
            )
            if len(domain_docs) >= 3:
                d_texts = [d.content or "" for d in domain_docs]
                d_labels = [d.domain for d in domain_docs]
                d_model, d_vec, d_metrics = engine.train_domain_model(d_texts, d_labels)
                engine.save_model(d_model, d_vec, d_metrics["classes"], "domain")
            print("Bootstrap: ML models warmed.")
    except Exception as exc:  # pragma: no cover - model training must not block boot
        print(f"Bootstrap: ML models skipped ({exc}).")
