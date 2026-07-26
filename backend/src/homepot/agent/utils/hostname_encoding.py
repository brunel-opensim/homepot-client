"""IDNA (Internationalised Domain Names in Applications) encoding utilities.

Ensures non-ASCII hostnames are converted to ASCII Punycode before being
used in HTTP requests.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def idna_encode(host: str) -> str:
    """Encode a non-ASCII hostname to its ASCII Punycode form.

    If the hostname is already ASCII it is returned unchanged.
    If encoding fails the original value is logged and returned as-is.

    Parameters
    ----------
    host:
        Hostname or IP address (with optional port).

    Returns
    -------
    ASCII-encoded hostname (with port preserved if present).
    """
    if not host:
        return host

    try:
        host.encode("ascii")
        return host
    except UnicodeEncodeError:
        pass

    port: Optional[str] = None
    if ":" in host:
        host, port = host.rsplit(":", 1)

    try:
        import idna

        encoded = idna.encode(host).decode("ascii")
    except ImportError:
        encoded = host
    except Exception as exc:
        logger.warning("Failed to IDNA-encode hostname %r: %s", host, exc)
        return f"{host}:{port}" if port else host

    result = f"{encoded}:{port}" if port else encoded
    logger.debug("IDNA-encoded hostname %r -> %r", host, result)
    return result


def idna_encode_url(url: str) -> str:
    """IDNA-encode the hostname portion of a URL.

    Handles URLs with ``http://`` or ``https://`` schemes.
    If the hostname is already ASCII or no scheme is found, the URL
    is returned unchanged.

    Parameters
    ----------
    url:
        URL string that may contain a non-ASCII hostname.

    Returns
    -------
    URL with the hostname IDNA-encoded.
    """
    if not url:
        return url

    for scheme in ("https://", "http://"):
        if url.lower().startswith(scheme):
            prefix = url[: len(scheme)]
            rest = url[len(scheme) :]
            hostname_end = rest.find("/")
            if hostname_end == -1:
                hostname_end = rest.find("?")
            if hostname_end == -1:
                hostname_end = rest.find("#")
            if hostname_end == -1:
                hostname = rest
                suffix = ""
            else:
                hostname = rest[:hostname_end]
                suffix = rest[hostname_end:]
            encoded_host = idna_encode(hostname)
            return f"{prefix}{encoded_host}{suffix}"

    return url
