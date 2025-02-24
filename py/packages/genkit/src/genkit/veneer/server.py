# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Functionality used by the Genkit veneer to start multiple servers.

The following servers may be started depending upon the host environment:

- Reflection API server.
- Flows server.

The reflection API server is started only in dev mode, which is enabled by the
setting the environment variable `GENKIT_ENV` to `dev`. By default, the
reflection API server binds and listens on (localhost, 3100).  The flows server
is the production servers that exposes flows and actions over HTTP.
"""

import asyncio
import atexit
import os
import os.path
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from asgiref.typing import ASGIApplication
from genkit.core.constants import DEFAULT_GENKIT_VERSION
from pydantic import BaseModel, ConfigDict, Field
from uvicorn.config import Config
from uvicorn.server import Server

# The version of the reflection API.
REFLECTION_API_SPEC_VERSION = 1


@dataclass
class ServerSpec:
    """ServerSpec encapsulates the scheme, host and port information.

    This class defines the server binding and listening configuration.
    """

    port: int
    scheme: str = 'http'
    host: str = 'localhost'

    @property
    def url(self) -> str:
        """URL evaluates to the host base URL given the server specs."""
        return f'{self.scheme}://{self.host}:{self.port}'


class RuntimeFileData(BaseModel):
    """Encapsulates the runtime file information stored by a Genkit instance.

    Attributes:
        genkit_version: The version of Genkit in use by the application.
        id: The ID of the runtime.
        pid: The PID of the process.
        reflection_api_spec_version: The version of the reflection API.
        reflection_server_url: The URL associated with the reflection server.
        timestamp: A timestamp.
    """

    model_config = ConfigDict(populate_by_name=True)

    genkit_version: str = Field(DEFAULT_GENKIT_VERSION, alias='genkitVersion')
    id: str = Field(..., alias='id')
    pid: int = Field(..., alias='pid')
    reflection_api_spec_version: int = Field(
        default=REFLECTION_API_SPEC_VERSION,
        alias='reflectionApiSpecVersion',
    )
    reflection_server_url: str = Field(..., alias='reflectionServerUrl')
    timestamp: str = Field(..., alias='timestamp')


def create_runtime(
    logger: Any,
    working_dir: str,
    reflection_server_spec: ServerSpec,
    at_exit_fn: Callable[[Path], None] | None = None,
    encoding='utf-8',
) -> Path:
    """Create a runtime configuration for use with the genkit CLI.

    The runtime information is stored in the form of a timestamped JSON file.
    Note that the file will be cleaned up as soon as the program terminates.

    Args:
        logger: An structlog logger instance.
        working_dir: The directory to create the runtime file in.
        reflection_server_spec: The server specification for the reflection
            server.
        at_exit_fn: A function to call when the runtime file is deleted.

    Returns:
        A path object representing the created runtime metadata file.
    """
    runtime_dir = os.path.join(working_dir, '.genkit/runtimes')
    if not os.path.exists(runtime_dir):
        os.makedirs(runtime_dir)

    current_datetime = datetime.now()
    runtime_file_name = f'{current_datetime.isoformat()}.json'
    runtime_file_path = Path(os.path.join(runtime_dir, runtime_file_name))
    pid = os.getpid()
    logger.info('Creating runtime file', runtime_file_path=runtime_file_path)
    data = RuntimeFileData(
        id=str(pid),
        pid=pid,
        reflection_server_url=reflection_server_spec.url,
        timestamp=current_datetime.isoformat(),
    )
    logger.info('Runtime file data', data=data)
    encoded = data.model_dump_json(by_alias=True)
    logger.info('Encoded runtime file data', encoded=encoded)
    runtime_file_path.write_text(encoded, encoding=encoding)
    logger.info('Wrote runtime file', runtime_file_path=runtime_file_path)

    if at_exit_fn:
        logger.info('Registering atexit function', at_exit_fn=at_exit_fn)

        def _atexit_fn():
            logger.info(
                'Running atexit function', runtime_file_path=runtime_file_path
            )
            at_exit_fn(runtime_file_path)

        atexit.register(_atexit_fn)
    return runtime_file_path


async def run_server_uvicorn(
    logger: Any, app_name: str, app: ASGIApplication, host: str, port: int
) -> None:
    """Runs an ASGI server instance using uvicorn.

    Args:
        logger: An async structlog logger instance.
        app_name: The name of the application server.
        app: The application server function (ASGI).
        host: The host to bind to.
        port: The port to listen on.

    Returns:
        None
    """
    config = Config(
        app=app,
        host=host,
        port=port,
        log_level='info',
        access_log=True,
    )
    server = Server(config=config)

    await logger.ainfo(
        f'Server running for {app_name} on {host}:{port}',
        name=app_name,
        host=host,
        port=port,
    )

    # Run the server
    await server.serve()


async def run_server(
    logger: Any, app_name: str, app: ASGIApplication, host: str, port: int
) -> None:
    """Runs an ASGI server instance.

    Args:
        logger: An async structlog logger instance.
        app_name: The name of the application server.
        app: The application server function (ASGI).
        host: The host to bind to.
        port: The port to listen on.

    Returns:
        None
    """
    server = await asyncio.start_server(
        lambda r, w: handle_connection(r, w, app), host, port
    )

    await logger.ainfo(
        f'Server running for {app_name} on {host}:{port}',
        name=app_name,
        host=host,
        port=port,
    )
    await server.serve_forever()


async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    app: ASGIApplication,
) -> None:
    """Connection handler.

    Args:
        reader: Asynchronous stream reader.
        writer: Asynchronous stream writer.
        app: The ASGI application function.

    Returns:
        None
    """
    try:
        # Read HTTP request
        request_line = await reader.readline()
        method, path, _ = request_line.decode().strip().split(' ')

        # Read headers
        headers = {}
        while True:
            line = await reader.readline()
            if line == b'\r\n':
                break
            name, value = line.decode().strip().split(': ')
            headers[name.lower()] = value

        # Create ASGI scope
        scope = {
            'type': 'http',
            'method': method,
            'path': path,
            'headers': [[k.encode(), v.encode()] for k, v in headers.items()],
            'query_string': b'',  # Simplified for this example
        }

        # ASGI receive function
        async def receive() -> dict[str, Any]:
            """ASGI receive function."""
            return {
                'type': 'http.request',
                'body': await reader.read(),
                'more_body': False,
            }

        # ASGI send function
        async def send(message) -> None:
            """ASGI send function.

            Args:
                message: An ASGI message.

            Returns:
                None
            """
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = message.get('headers', [])
                writer.write(f'HTTP/1.1 {status} OK\r\n'.encode())
                for header in headers:
                    writer.write(_format_http_header(header))
                writer.write(b'\r\n')
            elif message['type'] == 'http.response.body':
                writer.write(message['body'])
                await writer.drain()
                writer.close()

        def _format_http_header(header: tuple[bytes, bytes]) -> bytes:
            """Format a single HTTP header tuple into bytes.

            Args:
                header: A tuple of (name, value) where both are bytes.

            Returns:
                The formatted header as bytes.
            """
            return f'{header[0].decode()}: {header[1].decode()}\r\n'.encode()

        # Call the ASGI application
        await app(scope, receive, send)

    except Exception as e:
        print(f'Error handling connection: {e}')
        writer.close()
