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
from typing import TYPE_CHECKING

from starlette.responses import FileResponse

from core import View, route


if TYPE_CHECKING:
    from starlette.requests import Request

    from server import Server


logger: logging.Logger = logging.getLogger(__name__)


class Web(View):
    def __init__(self, app: Server) -> None:
        self.app = app

    @route("/", methods=["GET"], prefix=False)
    async def homepage(self, request: Request) -> FileResponse:
        return FileResponse("web/pages/index.html")
