"""
Unit tests for the curriculum library endpoints.

No database and no embedding model: these cover request validation and the
shape of the SQL, which is where this file's predecessors went wrong. The
retrieval query in backend/services/rag.py was unrunnable for two independent
reasons at once — a bind parameter that never bound and a column of the wrong
type — and neither was visible without executing it. The search endpoint here
writes its SQL by hand for the same reasons, so it gets the same guard.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# A bind parameter immediately followed by a Postgres `::` cast. SQLAlchemy
# truncates the parameter name and the value silently never binds.
BROKEN_CAST = re.compile(r":[a-zA-Z_][a-zA-Z0-9_]*::")


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app

    with TestClient(app) as test_client:
        yield test_client


# ==================== SQL SHAPE ====================


def test_search_sql_uses_cast_not_double_colon():
    """
    The failure mode this guards against cost this project its entire search
    capability once already.
    """
    import inspect

    from backend.api.routes import library

    source = inspect.getsource(library.search_library)

    # Skip comments: the handler explains this very pitfall in prose, and the
    # explanation necessarily contains the pattern it warns about.
    offenders = [
        line.strip()
        for line in source.splitlines()
        if not line.strip().startswith("#") and BROKEN_CAST.search(line)
    ]

    assert not offenders, (
        "bind parameter followed by '::' — use CAST(:name AS type):\n"
        + "\n".join(offenders)
    )
    assert "CAST(:vector AS vector)" in source


def test_search_sql_binds_the_parameters_it_is_given():
    """Every :name in the statement must be one the handler supplies."""
    import inspect

    from backend.api.routes import library

    source = inspect.getsource(library.search_library)
    sql = source.split('sql_text(\n            f"""')[1].split('"""')[0]

    # The f-string's {where} is substituted before text() sees it; the filters it
    # can contain are known, so stand them in to parse the worst case.
    resolved = sql.replace(
        "{where}",
        "pc.grade_level = :grade AND pc.subject ILIKE :subject"
        " AND pc.metadata ->> 'medium' = :medium",
    )

    found = set(text(resolved)._bindparams)
    supplied = {"vector", "limit", "snippet", "grade", "subject", "medium"}

    assert found <= supplied, f"query binds {found - supplied}, which nothing supplies"
    assert {"vector", "limit", "snippet"} <= found


# ==================== REQUEST VALIDATION ====================


def test_library_listing_is_reachable_without_credentials(client):
    """
    Shared curriculum belongs to no school, so reading it needs no account —
    the same position as the guest chat and guest speech routes.
    """
    response = client.get("/api/v2/library")

    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {
        "books", "total_books", "total_chapters", "total_chunks", "grades", "subjects",
    }
    assert isinstance(body["books"], list)


def test_library_totals_agree_with_the_book_list(client):
    """A summary that disagrees with its own rows is worse than no summary."""
    body = client.get("/api/v2/library").json()

    assert body["total_books"] == len(body["books"])
    assert body["total_chapters"] == sum(b["chapters"] for b in body["books"])
    assert body["total_chunks"] == sum(b["chunks"] for b in body["books"])
    assert body["grades"] == sorted(set(body["grades"]))


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({}, "q is required"),
        ({"q": "a"}, "q below the 2-character minimum"),
        ({"q": "x" * 501}, "q above the 500-character maximum"),
        ({"q": "rust", "limit": 0}, "limit below 1"),
        ({"q": "rust", "limit": 51}, "limit above the cap"),
        ({"q": "rust", "grade": 0}, "grade below 1"),
        ({"q": "rust", "grade": 13}, "grade above 12"),
    ],
)
def test_search_rejects_out_of_range_requests(client, params, reason):
    """Each of these must be refused before anything loads a 2.5 GB model."""
    response = client.get("/api/v2/library/search", params=params)

    assert response.status_code == 422, reason


def test_search_accepts_the_boundaries(client):
    """The limits themselves are valid values, not rejected ones."""
    for params in ({"q": "ab", "limit": 1}, {"q": "rust", "limit": 50},
                   {"q": "rust", "grade": 1}, {"q": "rust", "grade": 12}):
        response = client.get("/api/v2/library/search", params=params)
        assert response.status_code == 200, f"{params} should be accepted"


def test_search_response_shape(client):
    """The query is echoed so a client can match a response to its request."""
    response = client.get("/api/v2/library/search", params={"q": "photosynthesis"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "photosynthesis"
    assert body["count"] == len(body["hits"])
    for hit in body["hits"]:
        assert 0.0 <= hit["similarity"] <= 1.0
        assert hit["text"]


def test_search_snippets_are_capped(client):
    """Whole chapters must not travel in a search response."""
    from backend.api.routes.library import SNIPPET_CHARS

    body = client.get("/api/v2/library/search", params={"q": "energy"}).json()

    for hit in body["hits"]:
        assert len(hit["text"]) <= SNIPPET_CHARS


def test_grade_filter_restricts_results(client):
    """
    Retrieval without a grade filter answers from wherever the wording matches,
    which for a class 6 student may be a class 12 chapter.
    """
    body = client.get(
        "/api/v2/library/search", params={"q": "numbers", "grade": 1}
    ).json()

    assert all(hit["grade"] == 1 for hit in body["hits"])
