"""Шапка отдельного Blogspot-поста поверх общей очистки и клавиш v22."""
from urllib.parse import urlsplit
from lxml import html
from .keyboard_chords import extract as previous,repair_markup
from .blogspot_post import bind,title_text
from ..cleaning import CleanText,extracted_text
from ..html_structure import choose_title,decode

VERSION='clean-v23-blogspot-uniform-candidate'


def extract(content:bytes|str,url:str=''):
    clean,metadata=previous(content,url)
    host=(urlsplit(url).hostname or '').removeprefix('www.')
    binding=None
    if host.endswith('.blogspot.com'):
        fixed,_=repair_markup(decode(content))
        binding=bind(html.fromstring(fixed),host)
    counts=dict(bound_blogspot_posts=int(binding is not None),
                unresolved_blogspot_posts=int(host.endswith('.blogspot.com') and binding is None),
                restored_blogspot_titles=0,replaced_blogspot_site_titles=0)
    if binding is not None:
        main,title=binding['main'],binding['title']
        tree=binding['post'].getroottree().getroot()
        old_title=choose_title(tree,main,host)
        raw=clean.raw
        if old_title is not title:
            external=old_title is not None and main not in old_title.iterancestors()
            if external:
                prefix='# '+title_text(old_title)+'\n\n'
                if not raw.startswith(prefix):
                    return clean,metadata|counts|dict(unresolved_blogspot_posts=1,clean_version=VERSION)
                raw=raw[len(prefix):];counts['replaced_blogspot_site_titles']=1
            raw='# '+title_text(title)+'\n\n'+raw
            clean=extracted_text(raw,code_blocks=clean.code_blocks)
            clean=CleanText(clean.raw,clean.norm.replace('\u00ad',''),clean.code_blocks)
            counts['restored_blogspot_titles']=1
        metadata=metadata|dict(title=' '.join(title.text_content().split()),title_source='DOM-Blogspot-post-title')
    return clean,metadata|counts|dict(clean_version=VERSION)
