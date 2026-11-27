"""Локальная языковая проверка; русская метка не означает допуска в корпус."""
from functools import lru_cache
import hashlib
from importlib.metadata import version
from pathlib import Path

POLICY = 'py3langid-0.4.0-russian-v1'
MODEL_SHA256 = 'f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963'


class RussianLanguageReview:
    def __init__(self):
        import py3langid
        from py3langid.langid import LanguageIdentifier, MODEL_FILE

        package_version = version('py3langid')
        if package_version != '0.4.0':
            raise ValueError('Языковая проверка требует py3langid==0.4.0')
        model_path = Path(py3langid.__file__).parent / MODEL_FILE
        model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if model_sha != MODEL_SHA256:
            raise ValueError('Изменена языковая модель')
        self.identifier = LanguageIdentifier.from_modelpath(model_path, norm_probs=False)
        self.fingerprint = dict(policy=POLICY, package_version=package_version,
                                model_sha256=model_sha, numpy_version=version('numpy'),
                                implementation_sha256={str(p.relative_to(model_path.parents[1])):
                                    hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(model_path.parents[1].rglob('*.py'))})

    def check(self, text):
        if not isinstance(text, str):
            raise TypeError('Нужен полный текст str')
        if not text.strip():
            language, runner_up, gap = 'und', None, None
        else:
            ranking = self.identifier.rank(text)
            language, first = ranking[0]
            runner_up, second = ranking[1]
            gap = float(first - second)
        return dict(policy=POLICY, language=language, runner_up=runner_up,
                    score_gap=gap, review_required=language != 'ru' or gap == 0,
                    admitted=False)


@lru_cache(maxsize=1)
def load_review(policy):
    if policy != POLICY:
        raise ValueError('Неизвестная политика языка')
    return RussianLanguageReview()
