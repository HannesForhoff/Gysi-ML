import uvicorn

from gysi_ml.api.app import create_app
from gysi_ml.config import get_settings


def main() -> None:
    settings = get_settings()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
