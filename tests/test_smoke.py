from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_required_application_modules_exist():
    for module in ("main.py", "streamlit_app.py", "data_loader.py", "vector_db.py"):
        assert (ROOT / module).is_file()


def test_environment_template_is_safe_to_share():
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in template
    assert "AQ." not in template
