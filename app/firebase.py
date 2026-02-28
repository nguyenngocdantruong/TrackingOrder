import firebase_admin
import os
from firebase_admin import credentials, firestore
from flask import current_app

_db = None

def init_firebase(app):
    global _db
    service_account_path = app.config['FIREBASE_SERVICE_ACCOUNT_JSON_PATH']
    project_id = app.config['FIREBASE_PROJECT_ID']

    if not firebase_admin._apps:
        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred, {
                'projectId': project_id,
            })
        else:
            # Fallback for environments where credentials might be provided via env vars
            # or integrated GCP auth
            firebase_admin.initialize_app()

    _db = firestore.client()
    return _db

def get_db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db
