from translator.heuristics import heuristic_translate


def test_heuristic_translation_still_works() -> None:
    response = heuristic_translate("function add(a, b) { return a + b; }", "javascript", "python")
    assert "def add" in response.translated_code
    assert response.warnings
