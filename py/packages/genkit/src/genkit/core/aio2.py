# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Asyncio helpers."""

import asyncio
from asyncio import FIRST_COMPLETED, Future, Queue, ensure_future, wait
from typing import Any, AsyncIterator


class Channel(AsyncIterator[Any]):
    """
    An asynchronous channel for sending and receiving values.

    This class provides an asynchronous queue-like interface, allowing
    values to be sent and received between different parts of an
    asynchronous program. It also supports closing the channel,
    which will signal to any receivers that no more values will be sent.
    """

    def __init__(self, maxsize: int = 0):
        """
        Initializes a new Channel.

        The channel is initialized with an internal queue to store values,
        a future to signal when the channel is closed, and an optional
        close future.

        Args:
            maxsize (int, optional): The maximum size of the queue. Defaults to
                0 (unlimited).
        """
        self.queue = Queue(maxsize=maxsize)
        self.closed = Future()
        self.__close_future = None

    def __aiter__(self):
        """Returns self as an async iterator."""
        return self

    async def __anext__(self) -> Any:
        """
        Retrieves the next value from the channel.

        If the queue is not empty, the value is returned immediately.
        Otherwise, it waits until a value is available or the channel is closed.

        Raises:
            StopAsyncIteration: If the channel is closed and no more values
                                are available.

        Returns:
            Any: The next value from the channel.
        """
        if not self.queue.empty():
            value = self.queue.get_nowait()
            self.queue.task_done()
            if value is None:
                raise StopAsyncIteration
            return value

        pop = ensure_future(self.__pop())
        if not self.__close_future:
            try:
                return await pop
            except asyncio.CancelledError:
                pop.cancel()
                raise StopAsyncIteration

        try:
            finished, _ = await wait(
                [pop, self.__close_future], return_when=FIRST_COMPLETED
            )
            if pop in finished:
                return pop.result()
            if self.__close_future in finished:
                pop.cancel()
                raise StopAsyncIteration()
            return await pop
        except asyncio.CancelledError:
            pop.cancel()
            raise StopAsyncIteration

    def send(self, value: Any):
        """
        Sends a value into the channel.

        The value is added to the internal queue.

        Args:
            value: The value to send.
        """
        return self.queue.put_nowait(value)

    def set_close_future(self, future: Future):
        """
        Sets a future that, when completed, will close the channel.

        Args:
            future (Future): The future to set.
        """
        self.__close_future = ensure_future(future)

        def cleanup(f):
            try:
                result = f.result()
                self.closed.set_result(result)
            except Exception as e:
                self.closed.set_exception(e)
            finally:
                # Ensure queue is closed by sending None
                try:
                    self.queue.put_nowait(None)
                except:
                    pass

        self.__close_future.add_done_callback(cleanup)

    async def __pop(self) -> Any:
        """
        Asynchronously retrieves a value from the queue.

        This method waits until a value is available in the queue.

        Raises:
            StopAsyncIteration: If a None value is retrieved,
                               indicating the channel is closed.

        Returns:
            Any: The retrieved value.
        """
        try:
            r = await self.queue.get()
            self.queue.task_done()
            if r is None:
                raise StopAsyncIteration
            return r
        except (asyncio.CancelledError, RuntimeError):
            raise StopAsyncIteration
