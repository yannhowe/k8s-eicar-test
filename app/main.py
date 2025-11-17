import os
import subprocess
from html import escape
from pathlib import Path
from flask import Flask, request, redirect, url_for, Response
from werkzeug.utils import secure_filename

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_DIR"] = UPLOAD_DIR

FORM_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 2rem; background: #f5f6fa; }}
        main {{ max-width: 480px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.08); }}
        h1 {{ margin-top: 0; }}
        form {{ display: flex; flex-direction: column; gap: 1rem; }}
        input[type="file"] {{ padding: 0.4rem; }}
        button {{ padding: 0.8rem 1.2rem; border: none; border-radius: 8px; background: #1b4bff; color: white; font-size: 1rem; cursor: pointer; }}
        button:hover {{ background: #163dcc; }}
        .note {{ font-size: 0.9rem; color: #555; }}
        textarea {{ width: 100%; min-height: 120px; font-family: monospace; padding: 0.8rem; }}
        pre {{ background: #111; color: #eee; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
        .result {{ margin-top: 2rem; }}
        .stderr {{ color: #ff9f43; }}
        .error {{ color: #d63031; }}
    </style>
</head>
<body>
    <main>
        <h1>{title}</h1>
        <p class="note">{description}</p>
        <form action="{action}" method="post" enctype="multipart/form-data">
            <input type="file" name="file" required />
            <button type="submit">Upload</button>
        </form>
        {extra}
    </main>
</body>
</html>"""
SHELL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Run Shell Command</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 2rem; background: #f5f6fa; }}
        main {{ max-width: 720px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.08); }}
        h1 {{ margin-top: 0; }}
        form {{ display: flex; flex-direction: column; gap: 1rem; }}
        textarea {{ width: 100%; min-height: 160px; font-family: monospace; padding: 0.8rem; }}
        button {{ padding: 0.8rem 1.2rem; border: none; border-radius: 8px; background: #1b4bff; color: white; font-size: 1rem; cursor: pointer; }}
        button:hover {{ background: #163dcc; }}
        .note {{ font-size: 0.9rem; color: #555; }}
        pre {{ background: #111; color: #eee; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
        .stderr {{ color: #ff9f43; }}
        .error {{ color: #d63031; }}
        .result {{ margin-top: 2rem; }}
    </style>
</head>
<body>
    <main>
        <h1>Run Bash Command</h1>
        <p class="note">Commands run inside /bin/bash within this container. Outputs are prefixed with stdout/stderr for clarity.</p>
        <form action="{action}" method="post">
            <label for="command">Command</label>
            <textarea id="command" name="command" required>{command}</textarea>
            <button type="submit">Run</button>
        </form>
        <p class="note"><a href="{upload_href}">Back to upload page</a></p>
        {result}
    </main>
</body>
</html>"""


def _error(message: str, status: int = 400) -> Response:
    return Response(message + "\n", status=status, mimetype="text/plain")


def _render_form(title: str, description: str, action: str, extra_html: str = "") -> Response:
    html = FORM_TEMPLATE.format(title=title, description=description, action=action, extra=extra_html)
    return Response(html, mimetype="text/html")


def _save_stream(file_storage, target_path: Path) -> None:
    """Write the uploaded file to disk using low-level os.write to avoid buffering the whole file."""
    fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        while True:
            chunk = file_storage.stream.read(1024 * 1024)  # 1 MiB chunks
            if not chunk:
                break
            os.write(fd, chunk)
    finally:
        os.close(fd)


def _handle_upload(save_func) -> Response:
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
    file.stream.seek(0)  # ensure we're at the start
    save_func(file, target_path)
    return Response(f"Stored {filename} to {target_path}\n", mimetype="text/plain")


@app.get("/")
def index() -> Response:
    return redirect(url_for("upload_os_form"))


@app.get("/upload")
def upload_form_alias() -> Response:
    return redirect(url_for("upload_os_form"))


@app.get("/upload-os")
def upload_os_form() -> Response:
    return _render_form(
        title="EICAR Upload",
        description="Upload a file (e.g., the EICAR test string). This path streams directly to disk in 1 MiB chunks.",
        action=url_for("upload_os"),
        extra_html=f'<p class="note"><a href="{url_for("shell_form")}">Need a bash shell? Run commands here.</a></p>',
    )


@app.post("/upload-os")
def upload_os() -> Response:
    return _handle_upload(_save_stream)


@app.post("/upload")
def upload() -> Response:
    return upload_os()


def _render_shell_form(command: str = "", result_html: str = "") -> Response:
    html = SHELL_TEMPLATE.format(
        action=url_for("shell_run"),
        upload_href=url_for("upload_os_form"),
        command=escape(command),
        result=result_html,
    )
    return Response(html, mimetype="text/html")


@app.get("/shell")
def shell_form() -> Response:
    return _render_shell_form()


@app.post("/shell")
def shell_run() -> Response:
    command = request.form.get("command", "").strip()
    if not command:
        return _render_shell_form(result_html='<p class="error">Please provide a command to run.</p>')

    try:
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=15,
        )
        stdout = escape(completed.stdout or "")
        stderr = escape(completed.stderr or "")
        result_html = (
            f'<section class="result">'
            f"<h2>Result (exit code {completed.returncode})</h2>"
            f"<h3>stdout</h3><pre>{stdout or '(empty)'}</pre>"
            f"<h3>stderr</h3><pre class=\"stderr\">{stderr or '(empty)'}</pre>"
            f"</section>"
        )
        return _render_shell_form(command=command, result_html=result_html)
    except subprocess.TimeoutExpired:
        return _render_shell_form(
            command=command,
            result_html='<p class="error">Command timed out after 15 seconds.</p>',
        )


@app.get("/healthz")
def healthz() -> Response:
    return Response("ok\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
