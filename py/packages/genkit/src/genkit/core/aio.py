# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Asyncio helpers."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class Channel[T](AsyncIterator[T]):
    """An iterator-like asynchronous channel for sending and receiving values.

    This class provides an iterator-like asynchronous channel, allowing values
    to be sent and received between different parts of an asynchronous program.
    It also supports closing the channel, which will signal to any receivers
    that no more values will be sent.
    """

    def __init__(self) -> None:
        """Initializes a new Channel.

        The channel is initialized with an internal queue to store values, a
        future to signal when the channel is closed, and an optional close
        future.
        """
        self.queue: asyncio.Queue[T] = asyncio.Queue()
        self.closed: asyncio.Future[Any] = asyncio.Future()

    def __aiter__(self) -> AsyncIterator[T]:
        """Dunder method for the asynchronous iterator protocol.

        Returns:
            The asynchronous iterator for the channel.
        """
        return self

    async def __anext__(self) -> T:
        """Asynchronously retrieves the next value from the channel.

        If the queue is not empty, the value is returned immediately.
        Otherwise, it waits until a value is available or the channel is closed.

        Raises:
            StopAsyncIteration: If the channel is closed and no more values are
            available.

        Returns:
            The next value from the channel.
        """
        if not self.queue.empty():
            return self.queue.get_nowait()

        pop = asyncio.ensure_future(self._pop())
        if not self._close_future:
            return await pop
        finished, _ = await asyncio.wait(
            [pop, self._close_future], return_when=asyncio.FIRST_COMPLETED
        )
        if pop in finished:
            return pop.result()

        if self._close_future in finished:
            raise StopAsyncIteration()
        return await pop

    def send(self, value: T) -> None:
        """Sends a value into the channel.

        The value is added to the internal queue.

        Args:
            value: The value to send.

        Raises:
            asyncio.QueueFull: If the queue is full.
            asyncio.QueueShutDown: If the queue is shut down.

        Returns:
            None
        """
        self.queue.put_nowait(value)

    def set_close_future(self, future: asyncio.Future[Any]) -> None:
        """Sets a future that, when completed, will close the channel.

        Args:
            future: The future to set.

        Returns:
            None
        """
        self._close_future = asyncio.ensure_future(future)
        self._close_future.add_done_callback(
            lambda f: self.closed.set_result(f.result())
        )

    async def _pop(self) -> T:
        """Asynchronously retrieves a value from the queue.

        This method waits until a value is available in the queue.

        Raises:
            StopAsyncIteration: If a None value is retrieved, indicating the
            channel is closed.

        Returns:
            The retrieved value.
        """
        value = await self.queue.get()
        self.queue.task_done()
        if not value:
            raise StopAsyncIteration
        return value
