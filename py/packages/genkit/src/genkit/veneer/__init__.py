# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Veneer package for managing server and client interactions.

This package provides functionality for managing server-side operations,
including server configuration, runtime management, and client-server
communication protocols.
"""

from genkit.core.plugin_abc import Plugin
from genkit.veneer.veneer import Genkit

__all__ = [
    'Genkit',
    'Plugin',
]
