# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Asynchronous HTTP utilities."""

import json
from collections.abc import Callable
from enum import StrEnum
from typing import Any


class HTTPHeader(StrEnum):
    """HTTP header names.

    Attributes:
        CONTENT_LENGTH: Standard HTTP header for specifying the content length.
        CONTENT_TYPE: Standard HTTP header for specifying the media type.
        X_GENKIT_VERSION: Custom header for tracking genkit version.
    """

    CONTENT_LENGTH = 'Content-Length'
    CONTENT_TYPE = 'Content-Type'
    X_GENKIT_VERSION = 'X-Genkit-Version'


class HTTPMethod(StrEnum):
    """Standard HTTP method names.

    Attributes:
        CONNECT: Standard HTTP CONNECT.
        DELETE: Standard HTTP DELETE.
        GET: Standard HTTP GET.
        HEAD: Standard HTTP HEAD.
        OPTIONS: Standard HTTP OPTIONS.
        PATCH: Standard HTTP PATCH.
        POST: Standard HTTP POST.
        PUT: Standard HTTP PUT.
        TRACE: Standard HTTP TRACE.
    """

    CONNECT = 'CONNECT'
    DELETE = 'DELETE'
    GET = 'GET'
    HEAD = 'HEAD'
    OPTIONS = 'OPTIONS'
    PATCH = 'PATCH'
    POST = 'POST'
    PUT = 'PUT'
    TRACE = 'TRACE'


async def json_response(
    body: Any, status: int = 200, headers: dict[str, str] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Helper to create JSON responses."""
    response_headers = [(HTTPHeader.CONTENT_TYPE, b'application/json')]
    if headers is not None:
        response_headers.extend([
            (k.encode(), v.encode()) for k, v in headers.items()
        ])

    return {
        'type': 'http.response.start',
        'status': status,
        'headers': response_headers,
    }, {
        'type': 'http.response.body',
        'body': json.dumps(body).encode(),
    }


async def empty_response(
    status: int = 200,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Helper to create empty responses."""
    return {
        'type': 'http.response.start',
        'status': status,
        'headers': [],
    }, {
        'type': 'http.response.body',
        'body': b'',
    }


async def read_json_body(receive: Callable) -> dict[str, Any]:
    """Helper to read JSON request body."""
    body = b''
    more_body = True

    while more_body:
        message = await receive()
        body += message.get('body', b'')
        more_body = message.get('more_body', False)

    return json.loads(body) if body else {}
