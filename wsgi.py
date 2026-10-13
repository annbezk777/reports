"""
WSGI entry point for Gunicorn
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "sape_app_entry", os.path.join(os.path.dirname(__file__), "app.py")
)
_sape_app_entry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sape_app_entry)
application = _sape_app_entry.app

if __name__ == "__main__":
    application.run()
