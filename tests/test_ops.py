from mordornotebook.ops import CellOperationStore


def test_cell_operation_store_roundtrip(tmp_path):
    store = CellOperationStore(root=tmp_path)
    op = store.create("code", "1 + 1", session_id="s1")
    assert op.status == "queued"
    rows = store.list(session_id="s1")
    assert len(rows) == 1
    applied = store.ack(op.id, status="applied")
    assert applied.status == "applied"
