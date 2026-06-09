from pathlib import Path

from mordornotebook.memory import summarize_object


def test_summarizes_basic_object():
    summary = summarize_object("thing", {"a": 1})
    assert summary["name"] == "thing"
    assert summary["kind"] == "dict"


def test_summarizes_path(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("hello", encoding="utf-8")
    summary = summarize_object("path", Path(path))
    assert summary["exists"] is True
    assert summary["size_bytes"] == 5


def test_summarizes_dataframe_if_pandas_available():
    pytest = __import__("pytest")
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"ticker": ["AAPL", "MSFT"], "pnl": [1.0, -0.5]})
    summary = summarize_object("panel", df)
    assert summary["shape"] == [2, 2]
    assert "head" in summary
