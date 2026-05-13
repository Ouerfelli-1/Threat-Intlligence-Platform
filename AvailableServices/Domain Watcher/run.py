from pathlib import Path
import subprocess
import sys


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"

APP_MODULE = "main:app"
HOST = "127.0.0.1"
PORT = "8080"

DEFAULT_REQUIREMENTS = """fastapi
uvicorn[standard]
jinja2
python-multipart
cryptography
dnspython
requests
apscheduler
beautifulsoup4
playwright
OTXv2
"""


def get_venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_exists() -> bool:
    return get_venv_python().exists()


def run_command(command: list[str], check: bool = True) -> int:
    print("Running:", " ".join(map(str, command)))
    result = subprocess.run(command, cwd=BASE_DIR)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.returncode


def ensure_requirements_file() -> None:
    if not REQUIREMENTS_FILE.exists():
        print("requirements.txt not found. Creating a default one...")
        REQUIREMENTS_FILE.write_text(DEFAULT_REQUIREMENTS, encoding="utf-8")


def create_venv() -> None:
    print("Creating virtual environment...")
    run_command([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_requirements() -> None:
    python_bin = get_venv_python()

    print("Upgrading pip...")
    run_command([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])

    print("Installing requirements...")
    run_command([str(python_bin), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def install_playwright() -> None:
    python_bin = get_venv_python()

    print("Installing Playwright browsers...")
    run_command([str(python_bin), "-m", "playwright", "install"])

    print("Installing Playwright system dependencies...")
    run_command([str(python_bin), "-m", "playwright", "install-deps"], check=False)


def run_app() -> None:
    python_bin = get_venv_python()

    print(f"Starting app on http://{HOST}:{PORT}")
    run_command([
        str(python_bin),
        "-m",
        "uvicorn",
        APP_MODULE,
        "--host",
        HOST,
        "--port",
        PORT,
        "--no-server-header",
    ], check=False)


def main() -> None:
    ensure_requirements_file()

    if not venv_exists():
        create_venv()

    install_requirements()
    install_playwright()
    run_app()


if __name__ == "__main__":
    main()