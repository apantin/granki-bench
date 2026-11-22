"""Счётчик следов нейротекста, версия v1 — как в пилоте Granki, без изменений.

Шаблоны — по проходу 7 «Следы нейросети» и штампам из справочников Granki (CC BY 4.0, см. NOTICE.md).
Это метрика плотности, а не приговор: законный приём тоже считается.
"""
import json, re, sys
from pathlib import Path

PATTERNS = {
    'антитеза «не X, а Y»': r'\bне (?:просто |только )?[^.,;:!?\n]{1,40}, а (?:скорее )?\w',
    'антитеза «X, а не Y»': r'\w, а не \w',
    '«это (не) про»': r'\bэто (?:не )?про\b',
    'оценочный анонс': r'(?:честн\w+ оговорк|важн\w+ нюанс|неприятн\w+ правд|хорош\w+ новост|ключев\w+ момент|прост\w+ вывод|главн\w+ вывод|самое интересное|и вот что важно|но главное)',
    'дежурная связка': r'(?:\bкроме того\b|\bболее того\b|стоит отметить|важно отметить|важно понимать|давайте разберёмся|в современном мире|итак,)',
    'канцелярит': r'\b(?:является|являются|осуществля\w+|данн(?:ый|ая|ое|ые|ого|ой|ом|ых) |в рамках|на сегодняшний день)\b',
    'оценочные слова': r'\b(?:ключев\w+|комфортн\w+|оптимальн\w+|эффективн\w+|уникальн\w+|идеальн\w+)\b',
    'вопрос-сам-ответ': r'\?\s+[А-ЯЁ][^.?!]{0,40}\.',
    'восклицание': r'!(?!\[)',
    'анонс раздела': r'(?:^|(?<=[.!?]\s))(?:Теперь|Сначала|Дальше|Далее|Перейд\w+|Начн\w+|Начнём|Об этом|Разберём)\b[^.\n]{0,70}\.\s*$',
    'хеджирование': r'\b(?:может быть|в определённой степени|во многом|как правило|в целом)\b',
    'ограничитель': r'\bне (?:проверял\w*|мерил\w*|измерял\w*|знаю|знаем|оценивал\w*|говорит|учитывал\w*)\b|\bданных мало\b|\bразные недели\b',
}


def prose(text: str) -> str:
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith(('|', '#')))
    return text


def grams(text, n=4):
    w = re.findall(r'\w+', text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def count(text: str, ref: str | None = None) -> dict:
    body = prose(text)
    copied = sorted(' '.join(g) for g in grams(body) & grams(ref)) if ref else []
    words = len(re.findall(r'\w+', body))
    hits = {k: re.findall(v, body, re.I | re.M) for k, v in PATTERNS.items()}
    total = sum(len(v) for v in hits.values())
    sentences = [s for s in re.split(r'(?<=[.!?…])\s+', body) if re.search(r'\w', s)]
    lengths = [len(re.findall(r'\w+', s)) for s in sentences]
    mean = sum(lengths) / max(1, len(lengths))
    sd = (sum((x - mean) ** 2 for x in lengths) / max(1, len(lengths))) ** 0.5
    return dict(words=words, markers=total, per_1000=round(1000 * total / max(1, words), 1),
                copied_4grams=len(copied), copied_examples=copied[:6],
                sentence_len_mean=round(mean, 1), sentence_len_cv=round(sd / mean, 2) if mean else 0,
                by_kind={k: len(v) for k, v in hits.items() if v},
                examples={k: v[:3] for k, v in hits.items() if v})
