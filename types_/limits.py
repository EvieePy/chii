"""Chii. A simple URL shortner with a focus on privacy.

Copyright (C) 2024  Mysty <evieepy@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeAlias, TypedDict

from starlette.requests import Request

from core.core import _Route

from .requests import ResponseType


__all__ = ("RateLimit", "ExemptCallable", "LimitDecorator", "T_LimitDecorator", "RateLimitData")


ExemptCallable: TypeAlias = Callable[[Request], Awaitable[bool]] | None
LimitDecorator: TypeAlias = Callable[[Any, Request], ResponseType] | _Route
T_LimitDecorator: TypeAlias = Callable[..., LimitDecorator]


class RateLimitData(TypedDict):
    rate: int
    per: int
    bucket: Literal["ip", "user"]
    exempt: ExemptCallable


class RateLimit(TypedDict):
    rate: int
    per: int
