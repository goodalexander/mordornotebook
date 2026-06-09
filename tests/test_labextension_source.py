from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_labextension_registers_mordor_menu_toolbar_and_open_panel_api():
    source = (ROOT / "mordornotebook" / "labextension_src" / "src" / "index.ts").read_text(encoding="utf-8")

    assert "mordornotebook:open-panel" in source
    assert "mainMenu.addMenu" in source
    assert "app.docRegistry.addWidgetExtension('Notebook'" in source
    assert "new MordorNotebookButtonExtension(app)" in source
    assert "openPanel: () => openMordorPanel(notebooks)" in source
    assert "kernel.requestExecute" in source
    assert "silent: true" in source
    assert "panel/markup" in source
    assert "renderPanelMarkup(html)" in source
    assert "mordor_panel_bootstrap" not in source
    assert "<navstrategies-repo>" not in source


def test_labextension_does_not_route_prompt_content_with_canned_handlers():
    source = (ROOT / "mordornotebook" / "labextension_src" / "src" / "index.ts").read_text(encoding="utf-8")

    forbidden = [
        "canHandle",
        "equityUniverseCells",
        "memoryInspectCells",
        "chartCells",
        "missingObjectCells",
        "recent returns chart",
        "fresh equity universe",
        "HotUniverseConfig",
        "DOES_NOT_EXIST",
        "wikimedia",
        "wikipedia",
        "pageview",
    ]
    for value in forbidden:
        assert value not in source
    assert "handled: false" in source
    assert "Prompt requires the selected managed agent backend." in source
