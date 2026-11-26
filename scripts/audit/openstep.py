#!/usr/bin/env python3
"""Minimal OpenStep/NeXT ASCII property-list parser (Xcode project.pbxproj).

plistlib only reads XML and binary property lists. Xcode projects use the old
ASCII format, so this module provides the small subset of the grammar that
pbxproj files use: dictionaries, arrays, quoted and bare strings, comments.
"""
from __future__ import annotations

import plistlib
import re
from typing import Any

_BARE = re.compile(r"[^\s;,=(){}\"<>]+")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


class OpenStepError(ValueError):
    """Raised when the text is not a valid OpenStep property list."""


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def fail(self, message: str) -> OpenStepError:
        line = self.text.count("\n", 0, self.pos) + 1
        return OpenStepError(f"{message} at line {line}")

    def skip(self) -> None:
        text, n = self.text, len(self.text)
        while self.pos < n:
            ch = text[self.pos]
            if ch.isspace():
                self.pos += 1
            elif text.startswith("/*", self.pos):
                end = text.find("*/", self.pos + 2)
                if end < 0:
                    raise self.fail("unterminated comment")
                self.pos = end + 2
            elif text.startswith("//", self.pos):
                end = text.find("\n", self.pos)
                self.pos = n if end < 0 else end + 1
            else:
                return

    def expect(self, ch: str) -> None:
        self.skip()
        if self.text[self.pos:self.pos + 1] != ch:
            raise self.fail(f"expected {ch!r}")
        self.pos += 1

    def quoted(self) -> str:
        quote = self.text[self.pos]
        self.pos += 1
        out: list[str] = []
        text, n = self.text, len(self.text)
        while self.pos < n:
            ch = text[self.pos]
            if ch == quote:
                self.pos += 1
                return "".join(out)
            if ch == "\\" and self.pos + 1 < n:
                nxt = text[self.pos + 1]
                out.append(_ESCAPES.get(nxt, nxt))
                self.pos += 2
            else:
                out.append(ch)
                self.pos += 1
        raise self.fail("unterminated string")

    def string(self) -> str:
        self.skip()
        if self.pos >= len(self.text):
            raise self.fail("unexpected end of input")
        if self.text[self.pos] in "\"'":
            return self.quoted()
        match = _BARE.match(self.text, self.pos)
        if not match:
            raise self.fail("expected a string")
        self.pos = match.end()
        return match.group(0)

    def value(self) -> Any:
        self.skip()
        if self.pos >= len(self.text):
            raise self.fail("unexpected end of input")
        ch = self.text[self.pos]
        if ch == "{":
            return self.dictionary()
        if ch == "(":
            return self.array()
        if ch == "<":
            end = self.text.find(">", self.pos)
            if end < 0:
                raise self.fail("unterminated data literal")
            data = self.text[self.pos + 1:end]
            self.pos = end + 1
            return "".join(data.split())
        return self.string()

    def dictionary(self) -> dict[str, Any]:
        self.pos += 1
        result: dict[str, Any] = {}
        while True:
            self.skip()
            if self.text[self.pos:self.pos + 1] == "}":
                self.pos += 1
                return result
            key = self.string()
            self.expect("=")
            result[key] = self.value()
            self.skip()
            if self.text[self.pos:self.pos + 1] == ";":
                self.pos += 1

    def array(self) -> list[Any]:
        self.pos += 1
        result: list[Any] = []
        while True:
            self.skip()
            if self.text[self.pos:self.pos + 1] == ")":
                self.pos += 1
                return result
            result.append(self.value())
            self.skip()
            if self.text[self.pos:self.pos + 1] == ",":
                self.pos += 1


def parse(text: str) -> Any:
    """Parse OpenStep text into dict/list/str values."""
    parser = _Parser(text)
    value = parser.value()
    parser.skip()
    if parser.pos != len(text):
        raise parser.fail("trailing data")
    return value


def loads(data: bytes) -> Any:
    """Parse XML, binary or OpenStep property-list bytes."""
    try:
        return plistlib.loads(data)
    except (plistlib.InvalidFileException, ValueError):
        return parse(data.decode("utf-8-sig"))
