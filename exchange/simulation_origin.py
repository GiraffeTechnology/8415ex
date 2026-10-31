"""Host-owned HTTPS origin binding; no forwarded-header or caller authority."""
import ipaddress
import re
from urllib.parse import urlsplit


def canonical_public_origin(value):
    if value is None:
        return None
    if type(value) is not str or not value.isascii() or len(value) > 261:
        raise ValueError('explicit canonical HTTPS origin required')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme != 'https' or not host or parsed.username is not None
                or parsed.password is not None or parsed.port is not None
                or parsed.path or parsed.query or parsed.fragment
                or value != 'https://' + host):
            raise ValueError('explicit canonical HTTPS origin required')
        labels = host.split('.')
        if (len(labels) < 2 or len(host) > 253 or host.endswith('.localhost')
                or any(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) is None
                       for x in labels)):
            raise ValueError('canonical DNS host required')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return value
        raise ValueError('canonical DNS host required')
    except (TypeError, UnicodeError):
        raise ValueError('explicit canonical HTTPS origin required') from None
