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

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

import core
import views


if TYPE_CHECKING:
    from database import Database


logger: logging.Logger = logging.getLogger(__name__)


class Server(core.Application):
    def __init__(self, *, database: Database) -> None:
        self.database = database

        super().__init__(
            prefix=None,
            views=[views.Web(self), views.Redirects(self), views.API(self)],
            routes=[
                Mount("/static", app=StaticFiles(directory="web/static"), name="static"),
                Mount("/docs", app=StaticFiles(directory="docs"), name="docs"),
            ],
            middleware=[
                Middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                ),
                Middleware(
                    core.SessionMiddleware,
                    secret=core.config["SESSIONS"]["secret"],
                    max_age=core.config["SESSIONS"]["max_age"],
                ),
            ],
        )

    async def setup_hook(self) -> None:
        logger.info("Server has completed setup...")

    async def teardown(self) -> None:
        logger.info("Server is shutting down...")

    async def __aenter__(self) -> Self:
        await self.setup_hook()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.teardown()
