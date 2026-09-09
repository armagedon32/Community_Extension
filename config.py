import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "celmis-dev-secret-key-change-in-production")
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "celmis.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    # Maximum allowable amount for a single financial transaction (PHP).
    # Configured via environment variable so it can be tuned per deployment.
    MAX_TRANSACTION_AMOUNT = float(os.environ.get("MAX_TRANSACTION_AMOUNT", 500000))
