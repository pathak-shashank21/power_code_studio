from translator.validators import run_local_check


def test_sql_validator_handles_simple_create_table() -> None:
    result = run_local_check("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);", "sql", "sql")
    assert result.available is True
    assert result.passed is True


def test_vue_validator_reports_best_effort_message() -> None:
    result = run_local_check("<template><div>Hello</div></template>", "typescript", "vuejs")
    assert result.available is False
    assert "Vue" in result.detail
