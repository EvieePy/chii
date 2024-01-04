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
from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse, Response

from core import View, route


if TYPE_CHECKING:
    from starlette.requests import Request

    from server import Server
    from types_.requests import BasicRedirect


logger: logging.Logger = logging.getLogger(__name__)


class API(View):
    def __init__(self, app: Server) -> None:
        self.app = app

    @route("/create", methods=["POST"])
    async def create_url(self, request: Request) -> Response:
        try:
            data: dict[str, Any] = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "Unable to parse data.", "fields": {"required": "url", "optional": "expiry"}}, status_code=400
            )

        try:
            location: str = data["url"]
        except KeyError:
            return JSONResponse({"error": "Missing url field."}, status_code=400)

        payload: BasicRedirect = {"uid": None, "expiry": None, "location": location}
        identifier: str = await self.app.database.create_redirect(data=payload)

        # TODO: We probably shouldn't rely soley on request.url_for here and implement a fallback...
        return JSONResponse({"url": str(request.url_for("Redirects.redirect_base", id=identifier))})
