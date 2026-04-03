"""Star Command Web — Entry point Flask."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Logging su file come per la CLI
log_file = Path(__file__).parent / "star_command_web.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    filename=str(log_file),
    filemode="w",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("STAR_COMMAND_PORT", "5000"))
    debug = os.getenv("STAR_COMMAND_DEBUG", "false").lower() == "true"
    print(f"Star Command Web avviato su http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
