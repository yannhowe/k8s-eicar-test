import os
from pathlib import Path
from flask import Flask, request, redirect, url_for, Response
from werkzeug.utils import secure_filename

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_DIR"] = UPLOAD_DIR

FORM_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>EICAR Upload Harness</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 2rem; background: #f5f6fa; }
        main { max-width: 480px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.08); }
        h1 { margin-top: 0; }
        form { display: flex; flex-direction: column; gap: 1rem; }
        input[type=\"file\"] { padding: 0.4rem; }
        button { padding: 0.8rem 1.2rem; border: none; border-radius: 8px; background: #1b4bff; color: white; font-size: 1rem; cursor: pointer; }
        button:hover { background: #163dcc; }
        .note { font-size: 0.9rem; color: #555; }
    </style>
</head>
<body>
    <main>
        <h1>EICAR Upload Harness</h1>
        <p class=\"note\">Upload a file (for example the <a href=\"https://www.eicar.org/download-anti-malware-testfile/\" target=\"_blank\" rel=\"noopener noreferrer\">EICAR test string</a>). The server writes it directly to its local disk for downstream scanner testing.</p>
        <form action=\"/upload\" method=\"post\" enctype=\"multipart/form-data\">
            <input type=\"file\" name=\"file\" required />
            <button type=\"submit\">Upload</button>
        </form>
    </main>
</body>
</html>"""


def _error(message: str, status: int = 400) -> Response:
    return Response(message + "\n", status=status, mimetype="text/plain")


@app.get("/")
def index() -> Response:
    return Response(FORM_HTML, mimetype="text/html")


@app.post("/upload")
def upload() -> Response:
    if "file" not in request.files:
        return _error("Missing file part", 400)

    file = request.files["file"]
    if not file.filename:
        return _error("Empty filename", 400)

    filename = secure_filename(file.filename)
    if not filename:
        return _error("Filename rejected after sanitization", 400)

    target_path = app.config["UPLOAD_DIR"] / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    file.save(target_path)
    return Response(f"Stored {filename} to {target_path}\n", mimetype="text/plain")


@app.get("/healthz")
def healthz() -> Response:
    return Response("ok\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
