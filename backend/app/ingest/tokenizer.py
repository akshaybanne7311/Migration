"""Lexer for TMOS bigip.conf stanza syntax.

TMOS config files are not indentation-sensitive; structure comes entirely
from braces. A hand-rolled tokenizer (rather than regex-only parsing) is
used so brace depth and token boundaries are explicit and testable
independently of what any given token *means* -- this is what makes list
values (`vlans { a b }`) unambiguous from nested keyed blocks
(`profiles { http { context all } }`) one level up in the parser.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List


class TokenKind(str, Enum):
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    WORD = "WORD"
    QUOTED_STRING = "QUOTED_STRING"
    EOF = "EOF"


@dataclass
class Token:
    kind: TokenKind
    value: str
    line: int
    col: int


class TokenizeError(Exception):
    pass


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    line = 1
    col = 1
    i = 0
    n = len(text)

    def advance(count: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if i < n and text[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = text[i]

        if ch in " \t\r\n":
            advance()
            continue

        if ch == "#":
            while i < n and text[i] != "\n":
                advance()
            continue

        if ch == "{":
            tokens.append(Token(TokenKind.LBRACE, "{", line, col))
            advance()
            continue

        if ch == "}":
            tokens.append(Token(TokenKind.RBRACE, "}", line, col))
            advance()
            continue

        if ch == '"':
            start_line, start_col = line, col
            advance()  # consume opening quote
            chars = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    chars.append(text[i + 1])
                    advance(2)
                else:
                    chars.append(text[i])
                    advance()
            if i >= n:
                raise TokenizeError(
                    "Unterminated quoted string starting at "
                    "line %d col %d" % (start_line, start_col)
                )
            advance()  # consume closing quote
            tokens.append(
                Token(TokenKind.QUOTED_STRING, "".join(chars), start_line, start_col)
            )
            continue

        # bare WORD: run of chars until whitespace or a brace
        start_line, start_col = line, col
        chars = []
        while i < n and text[i] not in " \t\r\n{}\"":
            chars.append(text[i])
            advance()
        if chars:
            tokens.append(Token(TokenKind.WORD, "".join(chars), start_line, start_col))
        else:
            # a lone stray character we don't otherwise handle; skip defensively
            advance()

    tokens.append(Token(TokenKind.EOF, "", line, col))
    return tokens
