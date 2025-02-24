# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Veneer user-facing API for application developers who use the SDK."""

import asyncio
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import structlog
from genkit.ai.embedding import EmbedRequest, EmbedResponse
from genkit.ai.model import ModelFn
from genkit.core.action import ActionKind
from genkit.core.environment import is_dev_environment
from genkit.core.plugin_abc import Plugin
from genkit.core.reflection import make_reflection_app
from genkit.core.registry import Registry
from genkit.core.typing import (
    GenerateRequest,
    GenerateResponse,
    GenerationCommonConfig,
    Message,
)
from genkit.veneer.server import ServerSpec, create_runtime, run_server_uvicorn

# The reflection API server specification.
DEFAULT_REFLECTION_SERVER_SPEC = ServerSpec(
    scheme='http', host='127.0.0.1', port=3100
)

# The flow server specification.
DEFAULT_FLOW_SERVER_SPEC = ServerSpec(
    scheme='http', host='127.0.0.1', port=3400
)

# Default logger for the framework.
DEFAULT_LOGGER = structlog.get_logger(__name__)


class Genkit:
    """Veneer user-facing API for application developers who use the SDK."""

    def __init__(
        self,
        plugins: list[Plugin] | None = None,
        model: str | None = None,
        logger: Any = DEFAULT_LOGGER,
        working_dir: str | None = None,
        reflection_server_spec=DEFAULT_REFLECTION_SERVER_SPEC,
        flow_server_spec=DEFAULT_FLOW_SERVER_SPEC,
    ) -> None:
        """Initialize a new Genkit instance.

        Args:
            plugins: Optional list of plugins to initialize.
            model: Optional model name to use.
            logger: Optional async logger to use.
            working_dir: Optional working directory to use; the runtime will
                be initialized in a subdirectory of this directory.
            reflection_server_spec: Optional server spec for the reflection
                server.
            flow_server_spec: Optional server spec for the flow server.
        """
        self.logger = logger
        self.model = model
        self.registry = Registry()
        self.registry.default_model = model

        # NOTE: I'm not sure it makes sense to have multiple Genkit class
        # instances given each one initializes the runtime. Should we add a
        # check here to ensure we don't reinitialize the runtime if it has
        # already been initialized?
        if is_dev_environment():
            if working_dir is None:
                working_dir = os.getcwd()
            create_runtime(
                logger=self.logger,
                working_dir=working_dir,
                reflection_server_spec=reflection_server_spec,
                at_exit_fn=os.remove,
            )

        coro = self.start(plugins, reflection_server_spec, flow_server_spec)
        try:
            asyncio.run(coro)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')
            self.logger.info('Shutting down servers...')

    async def start(
        self,
        plugins: list[Plugin],
        reflection_server_spec: ServerSpec,
        flow_server_spec: ServerSpec,
    ) -> None:
        """Starts all the required servers and initializes all the plugins.

        Args:
            plugins: The list of plugins to load and initialize.
            reflection_server_spec: Server host and port information.
            flow_server_spec: Server host and port information.

        Returns:
            None
        """
        coroutines = [
            self.initialize_plugins(plugins),
        ]
        if is_dev_environment():
            coroutines.append(
                run_server_uvicorn(
                    self.logger,
                    'reflection server',
                    make_reflection_app(self.logger, self.registry),
                    reflection_server_spec.host,
                    reflection_server_spec.port,
                )
            )
        # TODO: Add flow server coroutine later.
        await asyncio.gather(*coroutines)

    async def initialize_plugins(self, plugins: list[Plugin]) -> None:
        """Initialize plugins for the Genkit instance.

        Args:
            plugins: The list of plugins implementing the Plugin interface.

        Returns:
            None
        """
        if not plugins:
            await self.logger.awarning('No plugins provided to Genkit')
        else:
            for plugin in plugins:
                if isinstance(plugin, Plugin):
                    # TODO: make this awaitable
                    await self.logger.adebug(
                        'Initializing plugin', plugin=plugin
                    )
                    await plugin.initialize(registry=self.registry)
                else:
                    raise ValueError(
                        f'Invalid {plugin=} provided to Genkit: '
                        f'must be of type `genkit.core.plugin_abc.Plugin`'
                    )

    async def generate(
        self,
        model: str | None = None,
        prompt: str | None = None,
        messages: list[Message] | None = None,
        system: str | None = None,
        tools: list[str] | None = None,
        config: GenerationCommonConfig | None = None,
    ) -> GenerateResponse:
        """Generate text using a language model.

        Args:
            model: Optional model name to use.
            prompt: Optional raw prompt string.
            messages: Optional list of messages for chat models.
            system: Optional system message for chat models.
            tools: Optional list of tools to use.
            config: Optional generation configuration.

        Returns:
            The generated text response.
        """
        model = model if model is not None else self.registry.defaultModel
        if model is None:
            raise Exception('No model configured.')
        if config and not isinstance(config, GenerationCommonConfig):
            raise AttributeError('Invalid generate config provided')

        model_action = self.registry.lookup_action(ActionKind.MODEL, model)
        return (
            await model_action.arun(
                GenerateRequest(messages=messages, config=config)
            )
        ).response

    async def embed(
        self, model: str | None = None, documents: list[str] | None = None
    ) -> EmbedResponse:
        """Calculates embeddings for the given texts.

        Args:
            model: Optional embedder model name to use.
            documents: Texts to embed.

        Returns:
            The generated response with embeddings.
        """
        embed_action = self.registry.lookup_action(ActionKind.EMBEDDER, model)

        return (
            await embed_action.arun(EmbedRequest(documents=documents))
        ).response

    def flow(self, name: str | None = None) -> Callable[[Callable], Callable]:
        """Decorator to register a function as a flow.

        Args:
            name: Optional name for the flow. If not provided, uses the
                function name.

        Returns:
            A decorator function that registers the flow.
        """

        def wrapper(func: Callable) -> Callable:
            flow_name = name if name is not None else func.__name__
            action = self.registry.register_action(
                name=flow_name,
                kind=ActionKind.FLOW,
                fn=func,
                span_metadata={'genkit:metadata:flow:name': flow_name},
            )

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return (await action.arun(*args, **kwargs)).response

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return action.run(*args, **kwargs).response

            return async_wrapper if action.is_async else sync_wrapper

        return wrapper

    def tool(
        self, description: str, name: str | None = None
    ) -> Callable[[Callable], Callable]:
        """Decorator to register a function as a tool.

        Args:
            description: Description for the tool to be passed to the model.
            name: Optional name for the flow. If not provided, uses the function name.

        Returns:
            A decorator function that registers the tool.
        """

        def wrapper(func: Callable) -> Callable:
            tool_name = name if name is not None else func.__name__
            action = self.registry.register_action(
                name=tool_name,
                kind=ActionKind.TOOL,
                description=description,
                fn=func,
            )

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return (await action.arun(*args, **kwargs)).response

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return action.run(*args, **kwargs).response

            return async_wrapper if action.is_async else sync_wrapper

        return wrapper

    def define_model(
        self,
        name: str,
        fn: ModelFn,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Define a custom model action.

        Args:
            name: Name of the model.
            fn: Function implementing the model behavior.
            metadata: Optional metadata for the model.
        """
        self.registry.register_action(
            name=name,
            kind=ActionKind.MODEL,
            fn=fn,
            metadata=metadata,
        )
