"""
Guards on the SQL that drives semantic search.

These need no database. They inspect how SQLAlchemy parses the query text,
which is where the bug lived: `:vector::vector` looks like a bind parameter
followed by a Postgres cast, but text() refuses to let a parameter name be
followed by a colon, so it backtracked and bound a parameter named "vecto".
The real value was passed as "vector", never matched, and every search failed
with "A value is required for bind parameter 'vecto'".

It is invisible on inspection and only shows up at runtime, so it is worth a
test that reads the parsed parameter names directly.
"""

import re
from pathlib import Path

from sqlalchemy import text

BACKEND = Path(__file__).resolve().parents[2] / "backend"
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

# A bind parameter immediately followed by a Postgres `::` cast.
BROKEN_CAST = re.compile(r":[a-zA-Z_][a-zA-Z0-9_]*::")


def test_sqlalchemy_mis_parses_a_bind_param_before_a_cast():
    """
    Pin the underlying behaviour, so the reason for CAST() stays legible.

    If a future SQLAlchemy accepts `:vector::vector`, this test fails and the
    workaround can be revisited deliberately rather than by accident.
    """
    statement = text("SELECT :vector::vector")

    assert "vector" not in statement._bindparams
    assert "vecto" in statement._bindparams


def test_cast_form_parses_the_parameter_correctly():
    """The form the code actually uses."""
    statement = text("SELECT CAST(:vector AS vector)")

    assert "vector" in statement._bindparams


def test_vector_search_query_binds_the_parameters_it_is_given():
    """
    The production query must ask for exactly the parameters
    _execute_vector_search supplies.
    """
    import inspect

    from backend.services.rag import RAGService

    body = inspect.getsource(RAGService._execute_vector_search)

    # Recover the SQL literal from the method and parse it the way SQLAlchemy will.
    sql = body.split('text("""')[1].split('""")')[0]
    statement = text(sql)

    assert set(statement._bindparams) == {"vector", "limit"}, (
        f"query binds {sorted(statement._bindparams)}; "
        "_execute_vector_search passes 'vector' and 'limit'"
    )


def test_no_bind_parameter_is_followed_by_a_postgres_cast():
    """
    Sweep backend/ and scripts/ for the pattern anywhere it could reappear.

    Comment lines are skipped so that prose explaining the bug — including the
    explanation in this file's own docstring and in rag.py — does not trip it.
    """
    sources = [
        p
        for p in list(BACKEND.rglob("*.py")) + list(SCRIPTS.rglob("*.py"))
        if "__pycache__" not in str(p)
    ]
    assert sources, "found no source files to scan; check the paths above"

    offenders = []
    for path in sorted(sources):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if BROKEN_CAST.search(line):
                offenders.append(f"  {path.name}:{lineno}: {stripped[:90]}")

    assert not offenders, (
        "bind parameter followed by '::' — SQLAlchemy truncates the parameter "
        "name and the value never binds. Use CAST(:name AS type).\n"
        + "\n".join(offenders)
    )
