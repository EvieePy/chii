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

from starlette.responses import HTMLResponse, JSONResponse, Response
from validators import ValidationError  # type: ignore
from validators.url import url as URLVALIDATOR  # type: ignore

from core import View, config, route
from core.exceptions import URLValidationError


if TYPE_CHECKING:
    from starlette.datastructures import UploadFile
    from starlette.requests import Request

    from server import Server
    from types_.requests import BasicRedirect


logger: logging.Logger = logging.getLogger(__name__)


class API(View):
    def __init__(self, app: Server) -> None:
        self.app = app

    def validate_url(self, __value: Any, /) -> str:
        options: dict[str, bool] = {
            "skip_ipv6_addr": True,
            "skip_ipv4_addr": True,
        }

        out: ValidationError | bool = URLVALIDATOR(__value, **options)
        if isinstance(out, ValidationError):
            raise URLValidationError from out

        if out is not True:
            raise URLValidationError

        max_: int = config["OPTIONS"]["max_url_length"]
        min_: int = config["OPTIONS"]["min_url_length"]
        len_: int = len(__value)

        if len_ > max_:
            raise URLValidationError(reason=f"The provided URL exceeds the maximum length of ({max_})")
        elif len_ < min_:
            raise URLValidationError(reason=f"The provided URL must be over ({min_}) characters long")

        return __value

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

        try:
            validated: str = self.validate_url(location)
        except URLValidationError as e:
            return JSONResponse(
                {"error": "An incorrect, invalid or improper URL was passed.", "extras": e.reason}, status_code=400
            )

        payload: BasicRedirect = {"uid": None, "expiry": None, "location": validated}
        identifier: str = await self.app.database.create_redirect(data=payload)

        # TODO: We probably shouldn't rely soley on request.url_for here and implement a fallback...
        return JSONResponse({"url": str(request.url_for("Redirects.redirect_base", id=identifier))})

    @route("/web/create", methods=["POST"])
    async def web_create_url(self, request: Request) -> Response:
        async with request.form() as form:
            location: UploadFile | str | None = form.get("url", None)

        try:
            validated: str = self.validate_url(location)
        except URLValidationError as e:
            error_html: str = """
            <p>
                <h3 class="error validationHeader">
                    Error:
                </h3>
                {reason}
            </p>
            """
            reason: str = e.reason or "The provided URL is invalid or forbidden!"
            return HTMLResponse(error_html.format(reason=reason), status_code=400)

        payload: BasicRedirect = {"uid": None, "expiry": None, "location": validated}
        identifier: str = await self.app.database.create_redirect(data=payload)

        # TODO: We probably shouldn't rely soley on request.url_for here and implement a fallback...
        short: str = str(request.url_for("Redirects.redirect_base", id=identifier))

        html: str = f"""
        <p>
            <h3 class="success validationHeader">
                Success:
            </h3>
            <a href="{short}">{short}</a>
        </p>
        """
        return HTMLResponse(html)
