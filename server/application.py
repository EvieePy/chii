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

import logging
from typing import TYPE_CHECKING, Any, Self

import core
import views


if TYPE_CHECKING:
    from database import Database


logger: logging.Logger = logging.getLogger(__name__)


class Server(core.Application):
    def __init__(self, *, database: Database) -> None:
        self.database = database
        super().__init__(prefix=None, views=[views.Redirects(self), views.API(self)])

    async def setup_hook(self) -> None:
        logger.info("Server is setting up...")

    async def teardown(self) -> None:
        logger.info("Server is shutting down...")

    async def __aenter__(self) -> Self:
        await self.setup_hook()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.teardown()
