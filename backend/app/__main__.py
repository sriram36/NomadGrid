import logging
import os

import uvicorn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  NomadGrid is starting on  http://localhost:{port}   (API docs: http://localhost:{port}/docs)\n")
    uvicorn.run("app.main:app", host=os.environ.get("HOST", "0.0.0.0"), port=port)
