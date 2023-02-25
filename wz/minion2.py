"""
minion.py

Last updated:  2023-01-01

Read MINION-formatted configuration data.

=+LICENCE=============================
Copyright 2023 Michael Towers

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
=-LICENCE========================================
"""

"""
MINION: MINImal Object Notation, v.2
------------------------------------

MINION is a simple configuration-file format taking ideas from JSON.

It contains structured data based on "dicts" (associative arrays), lists
and strings. Nothing else is supported. Files should be encoded as utf-8.

simple-string: A character sequence containing none of the following
    special characters:
        ' ': A separator.
        '#': Start a comment (until the end of the line).
        ':': Separates key from value in a dict.
        '{': Start a dict.
        '}': End a dict.
        '[': Start a list.
        ']': End a list.
        '"': Complex-string delimiter.

dict: { key:value key:value ... }
    A "key" is a simple-string.
    A "value" may be a simple-string, a complex-string, a list or a dict.

list: [ value value ... ]
    A "value" may be a simple-string, a complex-string, a list or a dict.

complex-string: " any characters ... "
    A complex-string may be continued from one line to the next. In that
    case trailing space characters are ignored and the continued string
    on the next line must start with '\'. Empty and comment lines will be
    ignored. Line breaks within a string are not directly supported –
    but provision is made for specifying escape characters: the basic
    escape sequences are '\/', '\"', '\n' and '\t' (for backslash,
    double-quote, newline and tab).

Spaces are not needed around the special characters, but they may
be used. Apart from within complex-strings and their use as separators,
spaces will be ignored.

Within the input lines all unicode control characters will be ignored.

The top level of a MINION text is a "dict" – without the surrounding
braces ({ ... }).

There is also a very limited macro-like feature. Elements declared at the
top level which start with '&' may be referenced (which basically means
included) at any later point in a data structure by means of the macro
name, e.g.:
    &MACRO1: [A list of words]
    ...
    DEF1: { X: &MACRO1 }
"""

### Messages
_BAD_DICT_LINE = "Ungültige Zeile (Schlüssel: Wert):\n  {line} – {text}"
_MULTI_KEY = "Schlüssel mehrfach definiert:\n  {line} – {key}"
_BAD_DICT_VALUE = "Ungültiger Schlüssel-Wert:\n  {line} – {val}"
_BAD_LIST_VALUE = "Ungültiger Listeneintrag:\n  {line} – {val}"
_BAD_STRINGX = "Ungültige Text-Zeile:\n  {line} – {text}"
_NO_KEY = "Schlüssel erwartet:\n  {line} – {text}"
_EARLY_END = "Vorzeitiges Ende der Eingabe in Zeile {line}:\n  {text}"
_NESTING_ERROR = "Datenstruktur nicht ordentlich abgeschlossen"
_NO_FILE = "MINION-Datei nicht gefunden:\n  {path}"
_BAD_FILE = "Ungültiges Datei-Format:\n  {path}"
_BAD_GZ_FILE = "Ungültiges Datei-Format (nicht 'gzip'):\n  {path}"
_FILEPATH = "\n  [in {path}]"
_BAD_MACRO = "Unbekanntes „Makro“: {line} – {val}"

### Special symbols, etc.
_COMMENT = "#"
_MACRO = "&"
_KEYSEP = ":"
_LIST0 = "["
_LIST1 = "]"
_DICT0 = "{"
_DICT1 = "}"
_DICTK = ":"
_STRING = '"'
_REGEX = r'(\s+|#|:|\[|\]|\{|\}|")'  # all special items
ESCAPE_DICT = {r"\n": "\n", r"\/": "\\", r"\"": '"', r"\t": "\t"}

from typing import Dict
import re, gzip, unicodedata

_RXSUB = "|".join([re.escape(e) for e in ESCAPE_DICT])

MACRO_BUILTINS: Dict[str, dict] = {}


class MinionError(Exception):
    pass


###


class Minion:
    """An impure recursive-descent parser for a MINION string.
    Usage:
        minion = Minion()
        python_dict = minion.parse(text)
    """

    #
    def report(self, message, **params):
        msg = message.format(**params)
        path = params.get("path")
        if (not path) and self.filepath:
            msg += _FILEPATH.format(path=self.filepath)
        raise MinionError(msg)

    #
    def parse(self, text, filepath=None):
        self.toplevel = None  # Needed for macros
        self.filepath = filepath
        self.line_number = 0
        self.lines = text.splitlines()
        data, rest = self.DICT(None)
        if rest or self.line_number < len(self.lines):
            self.report(
                _EARLY_END,
                line=self.line_number,
                text=self.lines[self.line_number - 1],
            )
        return data

    #
    def parse_file(self, fpath, **replacements):
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            self.report(_NO_FILE, path=fpath)
        except ValueError:
            self.report(_BAD_FILE, path=fpath)
        return self.parse_replace(text, fpath, **replacements)

    #
    def parse_replace(self, text, fpath, **params):
        for rep, val in params.items():
            text = text.replace(rep, val)
        return self.parse(text, fpath)

    #
    def parse_file_gz(self, fpath, **replacements):
        try:
            with gzip.open(fpath, "rt", encoding="UTF-8") as zipfile:
                text = zipfile.read()
        except FileNotFoundError:
            self.report(_NO_FILE, path=fpath)
        except OSError:
            self.report(_BAD_GZ_FILE, path=fpath)
        return self.parse_replace(text, fpath, **replacements)

    #
    def read_line(self):
        while True:
            if self.line_number >= len(self.lines):
                if self.line_number == len(self.lines):
                    # No more lines
                    self.line_number += 1
                    return _DICT1
                self.report(_NESTING_ERROR)
            line = self.lines[self.line_number]
            self.line_number += 1
            # "Strip" line and remove possible control characters.
            l = "".join(
                ch for ch in line.strip() if unicodedata.category(ch)[0] != "C"
            )
            if l:
                return l

    #
    def read_symbol(self, line):
        """Read up to the next "break-item" (space or special character
        or character sequence) on the current line.
        Return a triple: (pre-break-item, break-item, remainder)
        If there is no break-item or it is a comment, return
            (pre-break-item, None, None).
        """
        try:
            line = line.replace("\t", " ").strip()
            sym, sep, rest = re.split(_REGEX, line, 1)
        except:
            return line, None, None
        if sep == "#":
            # Comment
            return sym, None, None
        if sep[0] == " ":
            if rest.startswith("#"):
                # Comment
                return sym, None, None
            # If there is a space as break-item, use <None>.
            sep = None
        return sym, sep, rest

    #
    def DICT(self, line):
        dmap = {}
        if self.toplevel == None:
            self.toplevel = dmap  # Needed for macros
        while True:
            key, sep, rest = self.read_symbol(line)
            if sep == _DICTK:
                if not key:
                    self.report(_NO_KEY, line=self.line_number, text=line)
                if key in dmap:
                    self.report(_MULTI_KEY, line=self.line_number, key=key)
            elif sep == _DICT1 and not key:
                # End of DICT
                return dmap, rest
            else:
                if key or sep or rest:
                    self.report(
                        _BAD_DICT_LINE, line=self.line_number, text=line
                    )
                line = self.read_line()
                continue
            while not rest:
                rest = self.read_line()
            val, sep, rest2 = self.read_symbol(rest)
            if val:
                # A simple-string value ... or a macro
                if val[0] == _MACRO:
                    try:
                        dmap[key] = self.toplevel[val]
                    except KeyError:
                        try:
                            dmap[key] = MACRO_BUILTINS[val]
                        except KeyError:
                            self.report(
                                _BAD_MACRO, line=self.line_number, val=val
                            )
                else:
                    dmap[key] = val
                if sep == _DICT1:
                    return dmap, rest2
                elif sep:
                    self.report(
                        _BAD_DICT_LINE, line=self.line_number, text=line
                    )
            elif sep == _STRING:
                # A complex-string value
                dmap[key], rest2 = self.STRING(rest2)
            elif sep == _DICT0:
                # A sub-item (DICT or LIST)
                dmap[key], rest2 = self.DICT(rest2)
            elif sep == _LIST0:
                dmap[key], rest2 = self.LIST(rest2)
            else:
                self.report(_BAD_DICT_VALUE, line=self.line_number, val=rest)
            line = rest2

    #
    def STRING(self, line):
        lx = []
        while True:
            try:
                line, rest = re.split(r'(?<!\\)"', line, maxsplit=1)
                lx.append(line)
                s0 = "".join(lx)
                s0 = re.sub(_RXSUB, lambda m: ESCAPE_DICT[m.group(0)], s0)
                return s0, rest.lstrip()
            except ValueError:
                # no end, continue to next line
                lx.append(line)
            while True:
                # Empty lines and comment-lines are ignored
                line = self.read_line()
                if (not line) or line.startswith(_COMMENT):
                    continue
                if line[0] == "\\":  # Continuation line must start with '\'
                    line = line[1:]
                    break
                self.report(_BAD_STRINGX, line=self.line_number, text=line)

    #
    def LIST(self, line):
        lx = []
        while True:
            while not line:
                line = self.read_line()
            sym, sep, rest = self.read_symbol(line)
            if sym:
                # A simple-string value ... or a macro
                if sym[0] == _MACRO:
                    try:
                        lx.append(self.toplevel[sym])
                    except KeyError:
                        try:
                            lx.append(MACRO_BUILTINS[sym])
                        except KeyError:
                            self.report(
                                _BAD_MACRO, line=self.line_number, val=sym
                            )
                else:
                    lx.append(sym)
            if not sep:
                line = rest
                continue
            if sep == _LIST1:
                # End of list
                return lx, rest
            elif sep == _STRING:
                # A complex-string value
                sym, rest = self.STRING(rest)
            elif sep == _DICT0:
                # A DICT sub-item
                sym, rest = self.DICT(rest)
            elif sep == _LIST0:
                # A LIST sub-item
                sym, rest = self.LIST(rest)
            else:
                self.report(_BAD_LIST_VALUE, line=self.line_number, val=rest)
            lx.append(sym)
            line = rest


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    minion = Minion()
    data = minion.parse_file(
        "_test/data/test1.minion",
        _ABITUR_GRADES="[15 14 13 12 11 10 09 08 07"
        " 06 05 04 03 02 01 00 * n t nb /]",
    )
    for k, v in data.items():
        if k[0] == _MACRO:
            continue
        print("\n *** SECTION %s ***" % k)
        for k1, v1 in v.items():
            print("  ... %s: %s" % (k1, v1))
    print("TOPLEVEL:", minion.toplevel)

    print("\n ++ Test gzipped file ++")
    data = minion.parse_file_gz("_test/data/test2.minion.gz")
    print("\n???", data)
    quit(0)
    for k, v in data.items():
        print("\n *** SECTION %s ***" % k)
        for k1, v1 in v.items():
            print("  ... %s: %s" % (k1, v1))
