from app.ingest.tokenizer import TokenKind, tokenize


def test_braces_and_words():
    toks = tokenize("ltm pool /Common/p1 { members { } }")
    kinds = [t.kind for t in toks]
    assert kinds[:3] == [TokenKind.WORD, TokenKind.WORD, TokenKind.WORD]
    assert TokenKind.LBRACE in kinds
    assert TokenKind.RBRACE in kinds
    assert kinds[-1] == TokenKind.EOF


def test_comments_are_discarded():
    toks = tokenize("# a comment\nltm node /Common/n1 { address 10.1.1.1 }")
    values = [t.value for t in toks if t.kind == TokenKind.WORD]
    assert "#" not in " ".join(values)
    assert "ltm" in values


def test_quoted_string_with_space():
    toks = tokenize('description "hello world" { }')
    quoted = [t for t in toks if t.kind == TokenKind.QUOTED_STRING]
    assert len(quoted) == 1
    assert quoted[0].value == "hello world"


def test_line_tracking():
    toks = tokenize("a b\nc")
    a, b, c = toks[0], toks[1], toks[2]
    assert a.line == 1 and b.line == 1
    assert c.line == 2


def test_ipv6_word_not_split_by_tokenizer():
    toks = tokenize("destination /Common/2405:200:642:a699::76.5060")
    words = [t.value for t in toks if t.kind == TokenKind.WORD]
    assert "/Common/2405:200:642:a699::76.5060" in words
