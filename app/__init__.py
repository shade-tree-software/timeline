from flask import Flask

from . import config, db, routes


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(config.Config)

    db.init_app(app)
    app.register_blueprint(routes.bp)

    return app
