from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # Use socketio.run() instead of app.run() for WebSocket support
    socketio.run(app, debug=True, use_reloader=False, port=5000, host="0.0.0.0")
