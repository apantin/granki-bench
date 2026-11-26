"""Узкий предварительный URL-gate: сомнительное не считается принятой прозой."""
import re
from urllib.parse import unquote,urlsplit


VERSION='adult-url-review-v1'


def content_url_review(url:str)->bool:
    """Adult-маркеры/сексуальная фотогалерея требуют отдельной приёмки.

    Это удержание по метаданным, не доказательство содержимого/жанра и не
    общий NSFW-классификатор. Одна тема секса или подстрока не достаточны.
    """
    try:target=urlsplit(url)
    except ValueError:return False
    if target.scheme not in {'http','https'} or not target.hostname:return False
    tokens=set(re.findall(r'[^\W_]+',unquote(target.path).casefold()))
    if tokens & {'porn','porno','pornography','порно','порнография','hentai','хентай'}:return True
    sexual=tokens & {'minet','минет','sex','seks','seksa','секс','секса'}
    gallery=tokens & {'foto','фото','video','видео'}
    return bool(sexual and gallery and any(t.isdecimal() for t in tokens))
