import uvicorn
from app import app, DEFAULT_HOST, DEFAULT_PORT

uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
