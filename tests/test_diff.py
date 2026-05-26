from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def test_parses_added_file() -> None:
    diff = make_diff("foo/bar.py", ["import os", "print('hi')"])
    changes = parse_diff_text(diff)
    assert len(changes) == 1
    c = changes[0]
    assert c.path == "foo/bar.py"
    assert c.status == "added"
    assert [content for _, content in c.added_lines] == ["import os", "print('hi')"]
