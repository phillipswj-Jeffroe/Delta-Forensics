from app import app

def test_app_exists():
    assert app is not None

def test_app_is_flask():
    from flask import Flask
    assert isinstance(app, Flask)
