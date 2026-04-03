import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Global SocketIO instance (accessible from other modules)
socketio = SocketIO()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Ensure instance folder exists (for SQLite DB)
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize SocketIO with the app
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    # Initialize database
    from app.db import init_db
    init_db(app)

    # Register blueprint
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    # Register SocketIO events
    _register_socket_events()

    # Context processor — indices for sidebar/ticker
    from app.dummy_data import ALL_INDICES

    @app.context_processor
    def inject_indices():
        return {"indices": ALL_INDICES}

    # Template filter — relative timestamps ("2 hours ago")
    @app.template_filter("timeago")
    def timeago_filter(iso_string):
        if not iso_string:
            return ""
        try:
            dt = datetime.fromisoformat(str(iso_string))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = now - dt
            seconds = int(diff.total_seconds())

            if seconds < 0:
                return "just now"
            elif seconds < 60:
                return "just now"
            elif seconds < 3600:
                m = seconds // 60
                return f"{m} min ago"
            elif seconds < 86400:
                h = seconds // 3600
                return f"{h} hour{'s' if h != 1 else ''} ago"
            elif seconds < 604800:
                d = seconds // 86400
                return f"{d} day{'s' if d != 1 else ''} ago"
            else:
                return dt.strftime("%d %b %Y")
        except (ValueError, TypeError):
            return str(iso_string)

    # Start background news scheduler
    from app.services.scheduler import init_scheduler
    init_scheduler(app)

    # Start real-time WebSocket stream (market hours only)
    try:
        from app.services.realtime import init_realtime, start_stream
        init_realtime(socketio)
        start_stream()
    except Exception as e:
        logging.getLogger(__name__).warning("Real-time stream init failed: %s", e)

    return app


def _register_socket_events():
    """Register Socket.IO event handlers for the /live namespace."""
    from app.services.realtime import get_latest_prices

    @socketio.on("connect", namespace="/live")
    def on_connect():
        """Send latest cached prices when a client connects."""
        prices = get_latest_prices()
        if prices:
            for token, tick in prices.items():
                socketio.emit("tick", tick, namespace="/live")

    @socketio.on("disconnect", namespace="/live")
    def on_disconnect():
        pass
