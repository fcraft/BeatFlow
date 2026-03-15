"""Tests for HTTP Range media streaming helpers."""

import pytest
from fastapi import HTTPException

from app.utils.http_range import (
    build_bytes_stream_response,
    build_file_stream_response,
    parse_range_header,
)


class TestParseRangeHeader:
    def test_parse_standard_range(self):
        assert parse_range_header("bytes=10-19", 100) == (10, 19)

    def test_parse_open_ended_range(self):
        assert parse_range_header("bytes=95-", 100) == (95, 99)

    def test_parse_suffix_range(self):
        assert parse_range_header("bytes=-8", 100) == (92, 99)

    def test_invalid_range_raises_416(self):
        with pytest.raises(HTTPException) as exc:
            parse_range_header("bytes=100-10", 100)
        assert exc.value.status_code == 416

    def test_out_of_bounds_range_raises_416(self):
        with pytest.raises(HTTPException) as exc:
            parse_range_header("bytes=100-120", 100)
        assert exc.value.status_code == 416


class TestBytesRangeResponse:
    def test_partial_bytes_response_returns_206(self):
        response = build_bytes_stream_response(
            data=b"0123456789",
            media_type="audio/wav",
            filename="test.wav",
            range_header="bytes=2-5",
        )
        assert response.status_code == 206
        assert response.body == b"2345"
        assert response.headers["content-range"] == "bytes 2-5/10"
        assert response.headers["accept-ranges"] == "bytes"


@pytest.mark.asyncio
class TestFileRangeResponse:
    async def test_partial_file_response_returns_206(self, tmp_path):
        media_path = tmp_path / "sample.bin"
        media_path.write_bytes(b"abcdefghij")

        response = build_file_stream_response(
            path=str(media_path),
            media_type="audio/wav",
            filename="sample.wav",
            range_header="bytes=3-6",
        )

        body = b"".join([chunk async for chunk in response.body_iterator])
        assert response.status_code == 206
        assert body == b"defg"
        assert response.headers["content-range"] == "bytes 3-6/10"
        assert response.headers["content-length"] == "4"

    async def test_full_file_response_advertises_accept_ranges(self, tmp_path):
        media_path = tmp_path / "sample.bin"
        media_path.write_bytes(b"abcdefghij")

        response = build_file_stream_response(
            path=str(media_path),
            media_type="audio/wav",
            filename="sample.wav",
        )

        body = b"".join([chunk async for chunk in response.body_iterator])
        assert response.status_code == 200
        assert body == b"abcdefghij"
        assert response.headers["accept-ranges"] == "bytes"
