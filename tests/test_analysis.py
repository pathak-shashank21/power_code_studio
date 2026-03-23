from translator.analysis import detect_frameworks, extract_dependencies


def test_detects_frameworks_from_dependencies_and_code() -> None:
    deps = ["react", "next/navigation", "express"]
    frameworks = detect_frameworks(deps, code="const app = express(); useEffect(() => {}, []);")
    assert "reactjs" in frameworks
    assert "nextjs" in frameworks
    assert "expressjs" in frameworks


def test_extract_dependencies_sql_and_js() -> None:
    js = "import express from 'express'; const db = require('pg');"
    sql = "SELECT * FROM sales.orders JOIN hr.people ON people.id = orders.owner_id;"
    assert extract_dependencies(js, "javascript") == ["express", "pg"]
    sql_deps = extract_dependencies(sql, "sql")
    assert "sales.orders" in sql_deps
    assert "hr.people" in sql_deps
