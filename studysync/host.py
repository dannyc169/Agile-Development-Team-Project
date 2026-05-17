import os

from app import create_app, db
from dotenv import load_dotenv
load_dotenv()

def create_host_app():
    app = create_app()

    with app.app_context():
        db.create_all()

    return app


app = create_host_app()


def main():
    app.run(
        host=os.getenv("HOST_BIND", "0.0.0.0"),
        port=int(os.getenv("HOST_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )


if __name__ == "__main__":
    main()
