import os

from ombs.utils.env import load_dotenv


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "ANTHROPIC_API_KEY=sk-ant-from-file\n"
        'export QUOTED="hello world"\n'
        "BLANK_IGNORED\n"
        "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)

    assert load_dotenv(env_file) is True
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-from-file"
    assert os.environ["QUOTED"] == "hello world"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")

    load_dotenv(env_file)
    assert os.environ["ANTHROPIC_API_KEY"] == "from-shell"  # real env wins


def test_load_dotenv_missing_file_returns_false(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") is False
