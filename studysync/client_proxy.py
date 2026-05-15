import os
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

from flask import Flask, Response, request


def _build_target_url(path):
    host_base_url = os.getenv("HOST_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    target_path = f"/{path.lstrip('/')}"

    if request.query_string:
        target_path = f"{target_path}?{request.query_string.decode('utf-8')}"

    return f"{host_base_url}{target_path}"


def _copy_request_headers(parsed_target):
    excluded = {
        "host",
        "content-length",
        "connection",
        "accept-encoding",
    }

    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in excluded:
            headers[key] = value

    headers["Host"] = parsed_target.netloc
    return headers


def _forward_request(path):
    target_url = _build_target_url(path)
    parsed_target = urlsplit(target_url)

    connection_cls = HTTPSConnection if parsed_target.scheme == "https" else HTTPConnection
    connection = connection_cls(
        parsed_target.hostname,
        parsed_target.port or (443 if parsed_target.scheme == "https" else 80),
        timeout=60,
    )

    request_path = parsed_target.path or "/"
    if parsed_target.query:
        request_path = f"{request_path}?{parsed_target.query}"

    body = request.get_data()
    connection.request(
        method=request.method,
        url=request_path,
        body=body if body else None,
        headers=_copy_request_headers(parsed_target),
    )

    upstream_response = connection.getresponse()
    response_body = upstream_response.read()

    upstream_content_type = upstream_response.getheader("Content-Type")

    downstream_response = Response(
        response_body,
        status=upstream_response.status,
        content_type=upstream_content_type,
    )

    excluded_response_headers = {
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
    }

    for header_name, header_value in upstream_response.getheaders():
        if header_name.lower() not in excluded_response_headers and header_name.lower() != "content-type":
            downstream_response.headers.add(header_name, header_value)

    return downstream_response


def create_client_app():
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def proxy(path):
        return _forward_request(path)

    return app