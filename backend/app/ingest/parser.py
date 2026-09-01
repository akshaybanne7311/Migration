"""Recursive-descent parser for TMOS bigip.conf stanzas.

Turns a token stream into a generic tree (TmosStanza / TmosValue) with zero
domain knowledge of what a "Vip" or "Pool" is -- stanza_mappers.py is the
layer that interprets these generic trees as typed domain objects.

Disambiguation rule (the actual fix for "list-valued mappings reaching
string replacement"): F5's config writer always emits one logical entry
per source line. We use each token's line number -- not brace lookahead
alone -- to decide whether a body is a bare word list (`vlans { a b }`,
items on their own lines or packed on one line with no following value)
or a sequence of key(+value) entries (`address 10.1.1.1`, `http { }`).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union

from app.ingest.tokenizer import Token, TokenKind, tokenize

TmosValue = Union[str, List[str], Dict[str, Any]]


@dataclass
class TmosStanza:
    object_type: str
    object_name: str
    entries: Dict[str, TmosValue] = field(default_factory=dict)


class ParseError(Exception):
    pass


def _is_value_token(tok: Token) -> bool:
    return tok.kind in (TokenKind.WORD, TokenKind.QUOTED_STRING)


def _parse_block_body(tokens: List[Token], pos: int) -> Tuple[TmosValue, int]:
    """Parse the contents of a `{ ... }` block, up to (not including) the
    matching RBRACE. Returns (value, position_of_matching_RBRACE).
    """
    items: List[str] = []
    entries: Dict[str, TmosValue] = {}
    is_list = None  # None = undetermined, True = bare list, False = keyed
    p = pos

    while tokens[p].kind != TokenKind.RBRACE:
        first = tokens[p]
        if not _is_value_token(first):
            raise ParseError(
                "unexpected token %r at line %d" % (first.value, first.line)
            )
        nxt = tokens[p + 1]
        same_line = nxt.line == first.line

        if same_line and nxt.kind == TokenKind.LBRACE:
            # first is a KEY whose value is a nested block
            is_list = False if is_list is None else is_list
            key = first.value
            p += 2  # consume key + LBRACE
            block_val, p = _parse_block_body(tokens, p)
            p += 1  # consume matching RBRACE
            entries[key] = block_val

        elif same_line and _is_value_token(nxt):
            # first is a KEY with one or more scalar values on the same line
            is_list = False if is_list is None else is_list
            key = first.value
            p += 1
            same_line_words: List[str] = []
            while tokens[p].line == first.line and _is_value_token(tokens[p]):
                same_line_words.append(tokens[p].value)
                p += 1
            if tokens[p].kind == TokenKind.LBRACE:
                # compound value, e.g. `monitor min 1 of { m1 m2 }`
                p += 1
                block_val, p = _parse_block_body(tokens, p)
                p += 1
                entries[key] = {"_prefix": same_line_words, "_block": block_val}
            else:
                entries[key] = (
                    same_line_words[0] if len(same_line_words) == 1 else same_line_words
                )

        else:
            # first stands alone on its line: bare list item, or a flag key
            # with no value, depending on what this body has been so far.
            if is_list is False:
                entries[first.value] = None
                p += 1
            else:
                is_list = True
                items.append(first.value)
                p += 1

    return (items if is_list else entries), p


def parse_document(tokens: List[Token]) -> List[TmosStanza]:
    stanzas: List[TmosStanza] = []
    p = 0
    while tokens[p].kind != TokenKind.EOF:
        type_parts: List[str] = []
        while tokens[p].kind == TokenKind.WORD and not tokens[p].value.startswith("/"):
            type_parts.append(tokens[p].value)
            p += 1

        if _is_value_token(tokens[p]):
            object_name = tokens[p].value
            p += 1
        else:
            object_name = ""

        if tokens[p].kind != TokenKind.LBRACE:
            raise ParseError(
                "expected '{' after %r %r at line %d"
                % (" ".join(type_parts), object_name, tokens[p].line)
            )
        p += 1
        body, p = _parse_block_body(tokens, p)
        if tokens[p].kind != TokenKind.RBRACE:
            raise ParseError("unterminated block at line %d" % tokens[p].line)
        p += 1

        entries = body if isinstance(body, dict) else {}
        stanzas.append(
            TmosStanza(
                object_type=" ".join(type_parts),
                object_name=object_name,
                entries=entries,
            )
        )
    return stanzas


def parse_text(text: str) -> List[TmosStanza]:
    return parse_document(tokenize(text))
