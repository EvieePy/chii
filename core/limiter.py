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

import datetime
import logging
from typing import ClassVar


logger: logging.Logger = logging.getLogger(__name__)


class RateLimit:
    def __init__(self, rate: int, per: int) -> None:
        self.rate: int = rate
        self.period: datetime.timedelta = datetime.timedelta(seconds=per)

    @property
    def inverse(self) -> float:
        return self.period.total_seconds() / self.rate


class Store:
    __keys: ClassVar[dict[str, datetime.datetime]] = {}

    @classmethod
    def get_tat(cls, key: str, /) -> datetime.datetime:
        now: datetime.datetime = datetime.datetime.now(tz=datetime.UTC)
        return cls.__keys.get(key, now)

    @classmethod
    def set_tat(cls, key: str, /, *, tat: datetime.datetime) -> None:
        cls.__keys[key] = tat

    @classmethod
    def update(cls, key: str, limit: RateLimit) -> bool | float:
        now: datetime.datetime = datetime.datetime.now(tz=datetime.UTC)
        tat: datetime.datetime = max(cls.get_tat(key), now)

        separation: float = (tat - now).total_seconds()
        max_interval: float = limit.period.total_seconds() - limit.inverse

        if separation > max_interval:
            return separation

        new_tat: datetime.datetime = max(tat, now) + datetime.timedelta(seconds=limit.inverse)
        cls.set_tat(key, tat=new_tat)

        return False
