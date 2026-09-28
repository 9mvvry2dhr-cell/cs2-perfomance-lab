import unittest

from starlette.requests import Request

from src.api.app import (
    _request_is_cross_site_mutation,
)


def make_request(
    *,
    method: str,
    origin: str | None = None,
    fetch_site: str | None = None,
) -> Request:
    headers = [
        (
            b"host",
            b"cs2lab.ru",
        ),
    ]

    if origin is not None:
        headers.append(
            (
                b"origin",
                origin.encode("ascii"),
            )
        )

    if fetch_site is not None:
        headers.append(
            (
                b"sec-fetch-site",
                fetch_site.encode("ascii"),
            )
        )

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": "/analysis-jobs",
            "raw_path": b"/analysis-jobs",
            "query_string": b"",
            "headers": headers,
            "client": (
                "127.0.0.1",
                12345,
            ),
            "server": (
                "cs2lab.ru",
                443,
            ),
        }
    )


class CrossSiteMutationGuardTest(
    unittest.TestCase
):
    def test_same_origin_post_is_allowed(self):
        request = make_request(
            method="POST",
            origin="https://cs2lab.ru",
            fetch_site="same-origin",
        )

        self.assertFalse(
            _request_is_cross_site_mutation(
                request
            )
        )

    def test_cross_site_post_is_blocked(self):
        request = make_request(
            method="POST",
            origin="https://evil.example",
            fetch_site="cross-site",
        )

        self.assertTrue(
            _request_is_cross_site_mutation(
                request
            )
        )

    def test_safe_get_is_not_blocked(self):
        request = make_request(
            method="GET",
            origin="https://evil.example",
            fetch_site="cross-site",
        )

        self.assertFalse(
            _request_is_cross_site_mutation(
                request
            )
        )


if __name__ == "__main__":
    unittest.main()
