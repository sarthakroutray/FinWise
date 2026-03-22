import modal
import os

app = modal.App("finwise-backend")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("poppler-utils", "tesseract-ocr", "libgl1", "libglib2.0-0")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(".", remote_path="/root")
)

@app.function(
    image=image,
    timeout=300,
    secrets=[modal.Secret.from_dotenv()] 
)
@modal.asgi_app()
def fastapi_app():
    import os
    os.chdir("/root")
    from app.main import app as fastapi_instance
    return fastapi_instance
