import os
import warnings
from uuid import uuid4

from flask import Flask, render_template, redirect, request, url_for, session
from flask_login import current_user
from sassutils.wsgi import SassMiddleware

from . import htmx, bcrypt, login_manager, mail, db, SECRET_KEY, logger, models, categories, PAGE_LIMIT
from .routes import api, pages


def create_app():
    app = Flask(__name__)

    app.debug = os.getenv("DEBUG") == "1"

    logger.info(f"Debug mode: {app.debug}")

    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAIL_SERVER"] = "smtp-relay.sendinblue.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    # app.config["MAIL_USE_SSL"] = True
    app.config["MAIL_USERNAME"] = os.environ.get("EMAIL_USER")
    app.config["MAIL_PASSWORD"] = os.environ.get("EMAIL_PASS")
    assert app.config["MAIL_USERNAME"]
    assert app.config["MAIL_PASSWORD"]

    htmx.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: int) -> models.User:
        user = db.db_handler.get_user(user_id)
        return user

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        app.wsgi_app = SassMiddleware(app.wsgi_app, {
            "limbless": ("static/style/sass", "static/style/css", "/static/style/css")
        })

    @app.route("/index_page")
    def _index_page():
        return redirect(url_for("index_page"))

    @app.route("/")
    def index_page():
        if not current_user.is_authenticated:
            return redirect(url_for("auth_page.auth_page", next=url_for("index_page")))
            
        if current_user.is_insider():
            show_drafts = False
            _user_id = None
            recent_experiments, _ = db.db_handler.get_experiments(limit=PAGE_LIMIT, sort_by="id", descending=True)
        else:
            show_drafts = True
            _user_id = current_user.id
            recent_experiments = None

        recent_seq_requests, _ = db.db_handler.get_seq_requests(limit=PAGE_LIMIT, user_id=_user_id, sort_by="submitted_time", descending=True, show_drafts=show_drafts)

        return render_template(
            "index.html",
            recent_seq_requests=recent_seq_requests,
            recent_experiments=recent_experiments
        )

    @login_manager.unauthorized_handler
    def unauthorized():
        next = url_for(request.endpoint, **request.view_args)
        return redirect(url_for("auth_page.auth_page", next=next))
    
    @app.context_processor
    def inject_debug():
        return dict(debug=app.debug)
    
    @app.context_processor
    def inject_uuid():
        return dict(uuid4=uuid4)
    
    @app.context_processor
    def inject_categories():
        return dict(
            ExperimentStatus=categories.ExperimentStatus,
            SeqRequestStatus=categories.SeqRequestStatus,
        )
    
    @app.before_request
    def before_request():
        session["from_url"] = request.referrer

    # app.register_blueprint(api.jobs_bp)
    app.register_blueprint(api.samples_htmx)
    app.register_blueprint(api.projects_htmx)
    app.register_blueprint(api.experiments_htmx)
    app.register_blueprint(api.libraries_htmx)
    app.register_blueprint(api.auth_htmx)
    app.register_blueprint(api.organisms_htmx)
    app.register_blueprint(api.indices_htmx)
    app.register_blueprint(api.seq_requests_htmx)
    app.register_blueprint(api.adapters_htmx)
    app.register_blueprint(api.sequencers_htmx)
    app.register_blueprint(api.users_htmx)

    app.register_blueprint(pages.samples_page_bp)
    app.register_blueprint(pages.projects_page_bp)
    app.register_blueprint(pages.experiments_page_bp)
    app.register_blueprint(pages.libraries_page_bp)
    app.register_blueprint(pages.auth_page_bp)
    app.register_blueprint(pages.users_page_bp)
    app.register_blueprint(pages.seq_requests_page_bp)
    app.register_blueprint(pages.index_kits_page_bp)
    app.register_blueprint(pages.errors_bp)
    app.register_blueprint(pages.devices_page_bp)

    return app
