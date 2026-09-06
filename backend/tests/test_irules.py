from app.ingest.irules import extract_irule_scripts


def test_extracts_simple_irule_body_verbatim():
    text = """
ltm rule /Common/SIMPLE-RULE {
when HTTP_REQUEST {
    log local0. "hit"
}
}
"""
    scripts = extract_irule_scripts(text)
    assert set(scripts.keys()) == {"/Common/SIMPLE-RULE"}
    assert 'log local0. "hit"' in scripts["/Common/SIMPLE-RULE"]


def test_extracts_multiple_irules_with_nested_braces_and_comments():
    text = """
ltm rule /Common/RULE-ONE {
when HTTP_REQUEST {
    set dump [string tolower [HTTP::uri]]
    if { $dump eq "" } {
        # a comment mentioning a brace {
        persist source_addr 43200
    } else {
        persist uie "$dump"
    }
}
}
ltm rule /Common/RULE-TWO {
when CLIENT_ACCEPTED {
    log local0. "accepted"
}
}
"""
    scripts = extract_irule_scripts(text)
    assert set(scripts.keys()) == {"/Common/RULE-ONE", "/Common/RULE-TWO"}
    assert "persist source_addr 43200" in scripts["/Common/RULE-ONE"]
    assert "persist uie" in scripts["/Common/RULE-ONE"]
    assert "CLIENT_ACCEPTED" in scripts["/Common/RULE-TWO"]


def test_does_not_treat_ltm_virtual_or_pool_as_an_irule():
    text = """
ltm pool /Common/NOT-A-RULE {
    members { /Common/node1:80 { } }
}
"""
    assert extract_irule_scripts(text) == {}


def test_unbalanced_braces_are_skipped_not_truncated():
    text = "ltm rule /Common/BROKEN {\nwhen HTTP_REQUEST {\n    log local0. \"unterminated\"\n"
    assert extract_irule_scripts(text) == {}
