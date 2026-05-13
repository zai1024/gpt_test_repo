from __future__ import annotations

from flask import Flask

from app.config import settings
from app.models import db
from app.routes import bp
from app.scheduler import start_scheduler


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_AS_ASCII"] = False

    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    if settings.enable_scheduler:
        start_scheduler(app)

    return app
