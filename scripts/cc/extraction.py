"""Общие правила авторства и чтения одной записи WARC; без приватного реестра."""
import io
import re
from urllib.parse import urlsplit


def author_identity(url: str, metadata: dict) -> str:
    host = urlsplit(url).hostname or ''
    if host.endswith(('.livejournal.com', '.blogspot.com', '.wordpress.com')):
        return host
    path=urlsplit(url).path
    if host.endswith('teletype.in') and path.startswith('/@'):
        return host+path.split('/')[1]
    if host.endswith('liveinternet.ru') and path.startswith('/users/'):
        return host+'/users/'+path.split('/')[2]
    author = (metadata.get('author') or '').strip().casefold()
    if author and author not in {'admin', 'administrator'} and not re.match(r'^(?:редакция|команда)\b',author):
        return author
    return 'domain:' + host.removeprefix('www.')


def response_body(compressed: bytes) -> bytes:
    from warcio.archiveiterator import ArchiveIterator
    for record in ArchiveIterator(io.BytesIO(compressed)):
        if record.rec_type == 'response':
            return record.content_stream().read()
    return b''
