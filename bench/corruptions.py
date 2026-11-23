"""Детерминированные порчи: явная применимость, фактическая доза и происхождение."""
from __future__ import annotations
import hashlib
import random
import re
from dataclasses import dataclass
from .cleaning import markdown

VERSION = 'corrupt-v1'
DOSES = {'weak': .01, 'medium': .03, 'strong': .06}


@dataclass(frozen=True)
class Mutation:
    text: str
    changes: int
    eligible: int
    kind: str
    dose: str
    seed: int
    version: str = VERSION
    reason: str = ''


def mutate(text: str, kind: str, dose: str, seed: int) -> Mutation:
    if dose not in DOSES:
        raise ValueError('Неизвестная доза')
    rng = random.Random(seed)
    fraction = DOSES[dose]
    result = text
    count = eligible = 0
    if kind == 'typo':
        matches = list(re.finditer(r'\b[а-яё]{5,}\b', text))
        eligible = len(matches)
        chosen = rng.sample(matches, min(eligible, max(1, round(eligible*fraction))))
        for m in sorted(chosen, key=lambda x: x.start(), reverse=True):
            pos = m.start() + rng.randrange(1, len(m.group())-1)
            result = result[:pos] + result[pos]*2 + result[pos:]
        count = len(chosen)
    elif kind == 'punctuation':
        matches = list(re.finditer(r', (?=(?:что|поскольку|если|когда|потому что|котор(?:ый|ая|ое|ые|ого|ой|ых))\b)', text, re.I))
        eligible = len(matches)
        chosen = rng.sample(matches, min(eligible, max(1, round(eligible*min(1, fraction*10)))))
        for m in sorted(chosen, key=lambda x:x.start(), reverse=True):
            result = result[:m.start()] + ' ' + result[m.end():]
        count = len(chosen)
    elif kind == 'typography':
        matches = list(re.finditer(r'[«»—]', text))
        eligible = len(matches)
        chosen = rng.sample(matches, min(eligible, max(1, round(eligible*min(1, fraction*10)))))
        for m in sorted(chosen, key=lambda x:x.start(), reverse=True):
            result = result[:m.start()] + ('-' if m.group() == '—' else '"') + result[m.end():]
        count = len(chosen)
    elif kind == 'specificity':
        # Только счётные величины с родительным множественного; даты и имена не трогаются.
        matches = list(re.finditer(r'\b\d+ (?=(?:дней|часов|минут|рублей|процентов|лет|метров|месяцев|сотрудников|человек|случаев|пользователей)\b)', text))
        eligible = len(matches)
        chosen = rng.sample(matches, min(eligible, max(1, round(eligible*min(1, fraction*10)))))
        for m in sorted(chosen, key=lambda x:x.start(), reverse=True):
            result = result[:m.start()] + 'несколько ' + result[m.end():]
        count = len(chosen)
    elif kind in {'paragraph_order', 'repeat', 'structure'}:
        paragraphs = text.strip().split('\n\n')
        positions = [i for i,p in enumerate(paragraphs) if not p.lstrip().startswith(('#', '-', '[КОД]')) and len(p.split()) >= 15]
        eligible = len(positions)
        if kind == 'paragraph_order' and eligible >= 4:
            # Первое введение и все заголовки остаются на месте; перестановки в одном разделе.
            sections = []
            section = []
            for i,p in enumerate(paragraphs):
                if p.startswith('#'):
                    if len(section) >= 3: sections.append(section)
                    section = []
                elif i in positions: section.append(i)
            if len(section) >= 3: sections.append(section)
            if sections:
                group = rng.choice(sections)[1:]
                iterations = {'weak': 1, 'medium': 2, 'strong': max(2, len(group)//2)}[dose]
                for _ in range(iterations):
                    a,b = rng.sample(group, 2)
                    paragraphs[a],paragraphs[b] = paragraphs[b],paragraphs[a]
                count = iterations
                result = '\n\n'.join(paragraphs) + '\n'
        elif kind == 'repeat' and eligible:
            position = rng.choice(positions)
            repeat_count = {'weak': 1, 'medium': 2, 'strong': 3}[dose]
            paragraphs[position+1:position+1] = [paragraphs[position]]*repeat_count
            count = repeat_count
            result = '\n\n'.join(paragraphs) + '\n'
        elif kind == 'structure' and eligible >= 3:
            # Один вид изменения — склейка абзацев, без удаления заголовков.
            start = rng.choice(positions[:-1])
            limit = {'weak': 2, 'medium': 3, 'strong': 5}[dose]
            end = start+1
            while end < min(len(paragraphs), start+limit) and not paragraphs[end].startswith('#'):
                end += 1
            if end-start >= 2:
                count = end-start-1
                paragraphs[start:end] = [' '.join(paragraphs[start:end])]
                result = '\n\n'.join(paragraphs) + '\n'
    elif kind == 'sentence_order':
        paragraphs = text.strip().split('\n\n')
        candidates = []
        for i,p in enumerate(paragraphs):
            sentences = re.split(r'(?<=[.!?]) (?=[А-ЯЁ])', p)
            if len(sentences) >= 4 and not p.startswith(('#', '-')):
                candidates.append((i,sentences))
        eligible = len(candidates)
        if candidates:
            i,sentences = rng.choice(candidates)
            a,b = rng.sample(range(1,len(sentences)), 2)
            sentences[a],sentences[b] = sentences[b],sentences[a]
            paragraphs[i] = ' '.join(sentences)
            result = '\n\n'.join(paragraphs) + '\n'
            count = 1
    else:
        raise ValueError('Неизвестный вид порчи')
    if result == text:
        return Mutation(text, 0, eligible, kind, dose, seed, reason='not-applicable-or-no-change')
    return Mutation(result, count, eligible, kind, dose, seed)


def neutral_typography(text: str) -> tuple[str, str]:
    """Нейтральность только для norm; не для оценки авторской типографики."""
    norm = markdown(text).norm
    return norm, 'Тождественная нормализованная версия; контроль только для norm, не для raw-clean'


QUANTITY_VERSION='quantity-v2'
QUANTITY_UNITS=r'дней|часов|минут|рублей|процентов|лет|метров|месяцев|сотрудников|человек|случаев|пользователей'
QUANTITY_PATTERN=re.compile(r'\b\d+(?=[ \u00a0](?:'+QUANTITY_UNITS+r')\b)')
QUANTITY_GENITIVE={'из','от','до','около','более','менее','свыше','порядка','после','для','без','вместо','у',
                   'в течение','в продолжение','на протяжении'}
QUANTITY_ACCUSATIVE={'через','за','на','в'}
QUANTITY_GOVERNOR=re.compile(r'\b('+ '|'.join(re.escape(v) for v in sorted(QUANTITY_GENITIVE|QUANTITY_ACCUSATIVE,key=len,reverse=True))+r')[ \u00a0]+$',re.I)


def quantity_form(text: str,position: int) -> str | None:
    """Только явно заданное локальное управление; через границу строки не угадываем."""
    match=QUANTITY_GOVERNOR.search(text[max(0,position-80):position])
    if not match:return None
    return 'нескольких' if match[1].casefold() in QUANTITY_GENITIVE else 'несколько'


def mutate_quantity_v2(text: str,dose: str,seed: int) -> Mutation:
    """Числовая конкретика с ограниченным контролем падежа. Историческая v1 неизменна."""
    if dose not in DOSES:raise ValueError('Неизвестная доза')
    candidates=[]
    for match in QUANTITY_PATTERN.finditer(text):
        if int(match[0])==0:continue
        form=quantity_form(text,match.start())
        if form:candidates.append((match,form))
    n=min(len(candidates),max(1,round(len(candidates)*min(1,DOSES[dose]*10))))
    chosen=random.Random(seed).sample(candidates,n);result=text
    for match,form in sorted(chosen,key=lambda item:item[0].start(),reverse=True):
        result=result[:match.start()]+form+result[match.end():]
    return Mutation(result,len(chosen),len(candidates),'specificity',dose,seed,version=QUANTITY_VERSION,
                    reason='explicit-local-governor; semantic-and-human-validation-pending' if chosen else 'unsupported-context-or-no-count')
