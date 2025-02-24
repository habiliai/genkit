# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0


"""Development API for inspecting and interacting with Genkit.

This module provides a reflection API server for inspection and interaction
during development. It exposes endpoints for health checks, action discovery,
and action execution.
"""

from typing import Any

from asgiref.typing import (
    ASGIApplication,
    ASGIReceiveCallable,
    ASGISendCallable,
    Scope,
)
from genkit.core.action import ActionKind, create_action_key
from genkit.core.codec import dump_json
from genkit.core.constants import DEFAULT_GENKIT_VERSION
from genkit.core.registry import Registry
from genkit.core.web import (
    HTTPHeader,
    HTTPMethod,
    empty_response,
    json_response,
    read_json_body,
)


def make_reflection_app(
    logger: Any,
    registry: Registry,
    version=DEFAULT_GENKIT_VERSION,
    encoding='utf-8',
) -> ASGIApplication:
    """Create and return a ReflectionServer class with the given registry.

    Args:
        logger: An async structured logger.
        registry: The registry to use for the reflection server.
        version: The version string to use when setting the value of
            the X-GENKIT-VERSION HTTP header.
        encoding: The text encoding to use; default 'utf-8'.

    Returns:
        An asynchronous ASGI application that handles the reflection API.
    """

    async def app(
        scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope['type'] != 'http':
            return

        path = scope['path']
        method = scope['method']

        match (method, path):
            case (HTTPMethod.GET, '/api/__health'):
                # Health check endpoint
                start, body = await empty_response(200)
                await send(start)
                await send(body)
                return
            case (HTTPMethod.GET, '/api/actions'):
                # List all available actions
                actions = registry.list_serializable_actions()
                start, body = await json_response(actions)
                await send(start)
                await send(body)
                return
            case (HTTPMethod.POST, '/api/notify'):
                # TODO: Handle notifications
                start, body = await empty_response(200)
                await send(start)
                await send(body)
                return
            case (HTTPMethod.POST, '/api/runAction'):
                # Run an action
                payload = await read_json_body(receive)
                key = payload['key']
                action = registry.lookup_action_by_key(key)

                if action.kind == ActionKind.FLOW:
                    iput = payload['input']['start']['input']
                    input_action = action.input_type.validate_python(iput)
                else:
                    input_action = action.input_type.validate_python(
                        payload['input']
                    )

                output = action.fn(input_action)

                if isinstance(output.response, BaseModel):
                    result = output.response.model_dump(by_alias=True)
                    response_data = {
                        'result': result,
                        'traceId': output.trace_id,
                    }
                else:
                    response_data = {
                        'result': output.response,
                        'telemetry': {'traceId': output.trace_id},
                    }

                start, body = await json_response(
                    response_data,
                    headers={HTTPHeader.X_GENKIT_VERSION: version},
                )
                await send(start)
                await send(body)
                return
            case _:
                # 404 - Not found
                start, body = await json_response(
                    {'error': 'Not Found'}, status=404
                )
                await send(start)
                await send(body)

    return app
