from app import create_app
from app.services import sync_from_vcenter

app = create_app()

with app.app_context():
    run = sync_from_vcenter()
    print(f"{run.status}: {run.message}")
