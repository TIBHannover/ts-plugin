from unittest import TestCase
from unittest.mock import MagicMock, patch

from user_service.libs.safe_http import (
    SafeRequestError,
    read_limited,
    safe_get,
    safe_head,
)


class TestSafeHttp(TestCase):
    @patch("user_service.libs.safe_http.socket.getaddrinfo")
    def test_rejects_non_https_and_private_ipv4_and_ipv6(self, getaddrinfo):
        with self.assertRaises(SafeRequestError):
            safe_head("http://example.org/ontology.owl")

        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"):
            getaddrinfo.return_value = [(None, None, None, None, (address, 443))]
            with self.subTest(address=address), self.assertRaises(SafeRequestError):
                safe_head("https://example.org/ontology.owl")

    @patch("user_service.libs.safe_http.socket.getaddrinfo")
    def test_rejects_encoded_loopback_addresses(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 443))]
        for hostname in ("2130706433", "0x7f000001", "017700000001"):
            with self.subTest(hostname=hostname), self.assertRaises(SafeRequestError):
                safe_head(f"https://{hostname}/ontology.owl")

    @patch("user_service.libs.safe_http.urllib3.HTTPSConnectionPool")
    @patch("user_service.libs.safe_http.socket.getaddrinfo")
    def test_connects_to_the_validated_ip_without_resolving_again(self, getaddrinfo, pool):
        getaddrinfo.return_value = [
            (None, None, None, None, ("93.184.216.34", 443))
        ]
        pool.return_value.request.return_value = MagicMock(
            status=200, headers={"Content-Type": "text/turtle"}
        )

        safe_head("https://example.org/ontology.owl")

        getaddrinfo.assert_called_once()
        self.assertEqual(pool.call_args.args[:2], ("93.184.216.34", 443))
        self.assertEqual(pool.call_args.kwargs["server_hostname"], "example.org")
        self.assertEqual(pool.call_args.kwargs["assert_hostname"], "example.org")

    @patch("user_service.libs.safe_http.urllib3.HTTPSConnectionPool")
    @patch("user_service.libs.safe_http.socket.getaddrinfo")
    def test_revalidates_redirect_destinations(self, getaddrinfo, pool):
        getaddrinfo.side_effect = [
            [(None, None, None, None, ("93.184.216.34", 443))],
            [(None, None, None, None, ("127.0.0.1", 443))],
        ]
        pool.return_value.request.return_value = MagicMock(
            status=302, headers={"Location": "https://internal.example/secret"}
        )

        with self.assertRaises(SafeRequestError):
            safe_head("https://example.org/ontology.owl")

        self.assertEqual(getaddrinfo.call_count, 2)

    @patch("user_service.libs.safe_http.urllib3.HTTPSConnectionPool")
    @patch("user_service.libs.safe_http.socket.getaddrinfo")
    def test_enforces_response_size_limit(self, getaddrinfo, pool):
        getaddrinfo.return_value = [
            (None, None, None, None, ("93.184.216.34", 443))
        ]
        response = MagicMock(status=200, headers={})
        response.read.side_effect = [b"12345", b""]
        pool.return_value.request.return_value = response

        with self.assertRaises(SafeRequestError):
            safe_get("https://example.org/ontology.owl", max_bytes=4)

    def test_enforces_host_allowlist(self):
        with self.assertRaises(SafeRequestError):
            safe_head("https://example.org/ontology.owl", ["approved.example"])

    def test_enforces_stream_size_limit(self):
        with self.assertRaises(SafeRequestError):
            read_limited([b"123", b"45"], max_bytes=4)
