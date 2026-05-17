import os

from client_proxy import create_client_app


app = create_client_app()


def main():
    app.run(
        host=os.getenv("CLIENT_BIND", "0.0.0.0"),
        port=int(os.getenv("CLIENT_PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )


if __name__ == "__main__":
    main()
