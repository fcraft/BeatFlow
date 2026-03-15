"""HTTP Range helpers for media streaming endpoints."""

import os
import re
from collections.abc import Iterator
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
_CHUNK_SIZE = 64 * 1024


def parse_range_header(range_header: Optional[str], file_size: int) -> Optional[tuple[int, int]]:
    """Parse a single HTTP byte range.

    Supports forms like:
    - ``bytes=0-1023``
    - ``bytes=1024-``
    - ``bytes=-512``
    """
    if not range_header:
        return None

    if file_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="文件为空，无法处理 Range 请求",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    match = _RANGE_RE.match(range_header.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="无效的 Range 请求",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="无效的 Range 请求",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_text)
            end = file_size - 1 if not end_text else int(end_text)
            if start < 0 or end < start:
                raise ValueError
            if start >= file_size:
                raise HTTPException(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    detail="Range 起始位置超出文件大小",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )
            end = min(end, file_size - 1)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="无效的 Range 请求",
            headers={"Content-Range": f"bytes */{file_size}"},
        ) from exc

    return start, end


def _build_headers(
    *,
    filename: Optional[str],
    disposition: str,
    file_size: int,
    start: int,
    end: int,
    partial: bool,
) -> dict[str, str]:
    content_length = max(0, end - start + 1)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }
    if filename:
        # 非 ASCII 文件名需要 RFC 5987 编码，否则 Starlette 的 latin-1 编码会崩溃
        try:
            filename.encode("latin-1")
            # 纯 ASCII，直接用标准 filename
            headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        except UnicodeEncodeError:
            # 含非 ASCII 字符（如中文），使用 filename* 进行 UTF-8 百分号编码
            encoded = quote(filename, safe="")
            headers["Content-Disposition"] = (
                f"{disposition}; filename=\"download\"; filename*=UTF-8''{encoded}"
            )
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return headers


def _iter_file_range(path: str, start: int, end: int) -> Iterator[bytes]:
    with open(path, "rb") as fh:
        fh.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = fh.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def build_file_stream_response(
    *,
    path: str,
    media_type: str,
    filename: Optional[str] = None,
    disposition: str = "inline",
    range_header: Optional[str] = None,
):
    """Return a file response with byte-range support."""
    file_size = os.path.getsize(path)
    byte_range = parse_range_header(range_header, file_size)

    if file_size == 0:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": "0",
        }
        if filename:
            headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return Response(content=b"", media_type=media_type, headers=headers)

    start, end = byte_range or (0, file_size - 1)
    partial = byte_range is not None
    headers = _build_headers(
        filename=filename,
        disposition=disposition,
        file_size=file_size,
        start=start,
        end=end,
        partial=partial,
    )
    return StreamingResponse(
        _iter_file_range(path, start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK,
        media_type=media_type,
        headers=headers,
    )


def build_bytes_stream_response(
    *,
    data: bytes,
    media_type: str,
    filename: Optional[str] = None,
    disposition: str = "inline",
    range_header: Optional[str] = None,
):
    """Return an in-memory bytes response with byte-range support."""
    file_size = len(data)
    byte_range = parse_range_header(range_header, file_size)

    if file_size == 0:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": "0",
        }
        if filename:
            headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return Response(content=b"", media_type=media_type, headers=headers)

    start, end = byte_range or (0, file_size - 1)
    partial = byte_range is not None
    payload = data[start:end + 1]
    headers = _build_headers(
        filename=filename,
        disposition=disposition,
        file_size=file_size,
        start=start,
        end=end,
        partial=partial,
    )
    return Response(
        content=payload,
        status_code=status.HTTP_206_PARTIAL_CONTENT if partial else status.HTTP_200_OK,
        media_type=media_type,
        headers=headers,
    )
