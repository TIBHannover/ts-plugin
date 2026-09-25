import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import certifi
import urllib3


class SafeRequestError(Exception):
    pass


@dataclass
class SafeResponse:
    status_code: int
    headers: object
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def safe_head(url: str, allowed_hosts=None, max_redirects: int = 3) -> SafeResponse:
    return _request("HEAD", url, allowed_hosts, max_redirects, 0)


def safe_get(
    url: str,
    allowed_hosts=None,
    max_redirects: int = 3,
    max_bytes: int = 10 * 1024 * 1024,
) -> SafeResponse:
    return _request("GET", url, allowed_hosts, max_redirects, max_bytes)


def _request(method, url, allowed_hosts, max_redirects, max_bytes):
    current_url = url
    for redirect_count in range(max_redirects + 1):
        parsed, hostname, address = _validate_url(current_url, allowed_hosts)
        port = parsed.port or 443
        host_header = _host_header(hostname, port)
        pool = urllib3.HTTPSConnectionPool(
            address,
            port,
            server_hostname=hostname,
            assert_hostname=hostname,
            cert_reqs="CERT_REQUIRED",
            ca_certs=certifi.where(),
            timeout=urllib3.Timeout(connect=3, read=10),
            maxsize=1,
        )
        try:
            response = pool.request(
                method,
                urlunsplit(("", "", parsed.path or "/", parsed.query, "")),
                headers={"Host": host_header},
                redirect=False,
                preload_content=False,
                retries=False,
            )
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                response.close()
                if not location or redirect_count == max_redirects:
                    raise SafeRequestError("Too many redirects")
                current_url = urljoin(current_url, location)
                continue

            content = (
                b""
                if method == "HEAD"
                else read_limited(
                    iter(lambda: response.read(64 * 1024, decode_content=True), b""),
                    max_bytes,
                )
            )
            return SafeResponse(response.status, response.headers, content)
        except SafeRequestError:
            raise
        except Exception as exc:
            raise SafeRequestError("URL could not be fetched") from exc
        finally:
            pool.close()

    raise SafeRequestError("Too many redirects")


def _validate_url(url, allowed_hosts):
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii")
        port = parsed.port
    except (AttributeError, UnicodeError, ValueError) as exc:
        raise SafeRequestError("Invalid URL") from exc

    if parsed.scheme.lower() != "https" or not hostname or parsed.username or parsed.password:
        raise SafeRequestError("Only public HTTPS URLs are allowed")
    if allowed_hosts is not None and not _host_is_allowed(hostname, allowed_hosts):
        raise SafeRequestError("Host is not approved")
    if port is not None and not 1 <= port <= 65535:
        raise SafeRequestError("Invalid port")

    addresses = _resolve_addresses(hostname, port or 443)
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise SafeRequestError("Host does not resolve to a public address")
    return parsed, hostname, addresses[0]


def _resolve_addresses(hostname, port):
    try:
        return list(
            dict.fromkeys(
                result[4][0]
                for result in socket.getaddrinfo(
                    hostname, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
                )
            )
        )
    except socket.gaierror as exc:
        raise SafeRequestError("Host could not be resolved") from exc


def _host_is_allowed(hostname, allowed_hosts):
    hostname = hostname.lower()
    for allowed_host in allowed_hosts:
        allowed_host = allowed_host.strip().lower().rstrip(".")
        if hostname == allowed_host or (
            allowed_host.startswith("*.") and hostname.endswith(allowed_host[1:])
        ):
            return True
    return False


def _host_header(hostname, port):
    hostname = f"[{hostname}]" if ":" in hostname else hostname
    return hostname if port == 443 else f"{hostname}:{port}"


def read_limited(chunks, max_bytes):
    content = bytearray()
    for chunk in chunks:
        content.extend(chunk)
        if len(content) > max_bytes:
            raise SafeRequestError("Response is too large")
    return bytes(content)
