"""Типизированные клавиши в ошибочно неэкранированных HTML-скобках."""
import html,re
from html.parser import HTMLParser

MOD=r'(?:Ctrl|Control|Alt|Shift|Meta|Win|Cmd|Command)'
KEY=r'(?:'+MOD+r'|Tab|Esc|Escape|Enter|Return|Space|Backspace|Delete|Del|Insert|Ins|Home|End|PageUp|PageDown|Left|Right|Up|Down|F(?:[1-9]|1[0-2])|[A-Z0-9])'
CHORD=re.compile(r'<\s*'+MOD+r'(?:\s*\+\s*'+KEY+r')+\s*>',re.I|re.ASCII)
VOID=frozenset('area base br col embed hr img input link meta param source track wbr'.split())
SKIP=frozenset('script style pre code textarea title head noscript svg math template'.split())
PROSE=frozenset('p li td th h1 h2 h3 h4 h5 h6'.split())


class _Chords(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=False)
        self.text=text;self.stack=[];self.changes=[]
        self.starts=[0]+[m.end() for m in re.finditer('\n',text)]

    def handle_starttag(self,tag,attrs):
        raw=self.get_starttag_text()
        if CHORD.fullmatch(raw):
            if not SKIP.intersection(self.stack) and PROSE.intersection(self.stack):
                line,column=self.getpos();start=self.starts[line-1]+column
                assert self.text[start:start+len(raw)]==raw
                self.changes.append((start,start+len(raw),html.escape(raw,quote=False)))
            return
        if tag not in VOID:self.stack.append(tag)

    def handle_endtag(self,tag):
        if tag in self.stack:
            last=len(self.stack)-1-self.stack[::-1].index(tag)
            del self.stack[last:]

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        self.handle_endtag(tag)


def repair_markup(text):
    parser=_Chords(text);parser.feed(text);parser.close()
    result=text
    for start,end,replacement in reversed(parser.changes):result=result[:start]+replacement+result[end:]
    return result,len(parser.changes)


VERSION = 'clean-v22-keyboard-chords-candidate'


def extract(content: bytes | str, url: str = ''):
    """Отдельный кандидат: раскрыть исходные клавиши до DOM-разбора."""
    from ..html_structure import decode
    from .editorial_roles import extract as previous
    fixed, count = repair_markup(decode(content))
    clean, metadata = previous(fixed if count else content, url)
    return clean, metadata | dict(clean_version=VERSION, recovered_keyboard_chord_markup=count)
