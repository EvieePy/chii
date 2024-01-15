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

import asyncio
import io
import logging
from typing import TYPE_CHECKING, Any

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from starlette.responses import HTMLResponse, JSONResponse, Response
from validators import ValidationError  # type: ignore
from validators.url import url as URLVALIDATOR  # type: ignore

from core import View, config, limiter, route
from core.exceptions import URLValidationError


if TYPE_CHECKING:
    from starlette.datastructures import UploadFile
    from starlette.requests import Request

    from server import Server
    from types_ import Redirect
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

    def generate_qr(self, __value: str, /) -> io.BytesIO:
        qr = qrcode.QRCode(  # type: ignore
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # type: ignore
            box_size=10,
            border=4,
        )

        qr.add_data(__value)  # type: ignore

        img = qr.make_image(  # type: ignore
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(radius_ratio=1),
            color_mask=SolidFillColorMask(front_color=(119, 90, 165), back_color=(249, 241, 239)),
        )

        fp: io.BytesIO = io.BytesIO()
        img.save(fp, "PNG")  # type: ignore
        img.close()  # type: ignore

        fp.seek(0)
        return fp

    def generate_html(self, request: Request, /, *, identifier: str, should_qr: bool = False) -> str:
        # TODO: We probably shouldn't rely soley on request.url_for here and implement a fallback...
        short: str = str(request.url_for("Redirects.redirect_base", id=identifier))
        qr_url: str = str(request.url_for("API.display_qr_code", id=identifier))

        qr_html: str = ""

        if should_qr:
            qr_html = f"""
            <div class="innerDetails">
                <a href="/qr/{identifier}"><img src="/qr/{identifier}" class="qrDisplay"></a>
            </div>
            """

        html: str = f"""
        <p>
            <h3 class="success validationHeader">
                Generated URL:
            </h3>

            <div class="submitDetails">
                {qr_html}

                <div class="innerDetails">
                    <span><b>URL   :</b> <a id="copyURL" href="{short}">{short}</a></span>
                    {f'<span><b>QR URL:</b> <a href="/qr/{identifier}">{qr_url}</a></span>' if should_qr else ''}
                    <span id="_url_submit_button" class="standardButton" onclick="copyURLClipboard()">Copy URL</span>
                    {f'<a href="/qr/{identifier}" class="standardButton" download>Download QR</a>' if should_qr else ''}
                </div>
            </div>
        </p>
        """

        return html

    @route("/create", methods=["POST"])
    @limiter.limit(config["LIMITS"]["create"])  # type: ignore
    async def create_url(self, request: Request) -> Response:
        """Create a shortened URL via API.

        ---
        summary: Create a short URL.

        requestBody:
            description: The URL to shorten. URL must be between 25 and 1024 characters long.
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            url:
                                type: string
                                example: https://google.com?q=Pizza

        responses:
            200:
                description: The shortened URL data.
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                url:
                                    type: string
                                    example: https://chii.to/abc123
                                qr:
                                    type: string
                                    example: https://chii.to/qr/abc123
                                location:
                                    type: string
                                    example: https://google.com?q=Pizza
                                expiry:
                                    type: string
                                    example: 2024-01-01T00:00:00.000000+00:00
                                id:
                                    type: string
                                    example: abc123
                                views:
                                    type: integer
                                    example: 0
            400:
                description: The URL was invalid or missing.
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                error:
                                    type: string
                                    example: An incorrect, invalid or improper URL was passed.
                                extra:
                                    type: string
                                    example: The provided URL exceeds the maximum length of (1024)
        """
        try:
            data: dict[str, Any] = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "Unable to parse data.", "extra": '"required": "url", "optional": "expiry"'}, status_code=400
            )

        try:
            location: str = data["url"]
        except KeyError:
            return JSONResponse({"error": "Missing url field.", "extra": ""}, status_code=400)

        try:
            validated: str = self.validate_url(location)
        except URLValidationError as e:
            return JSONResponse(
                {"error": f"An incorrect, invalid or improper URL was passed: {e.reason}", "extra": e.reason},
                status_code=400,
            )

        payload: BasicRedirect = {"uid": None, "expiry": None, "location": validated}
        row: Redirect | None = await self.app.database.create_redirect(data=payload)

        if not row:
            return JSONResponse({"error": "Internal server error: (Database)"}, status_code=500)

        data = dict(row)
        data.pop("uid", None)

        data["url"] = str(request.url_for("Redirects.redirect_base", id=data["id"]))
        data["qr"] = str(request.url_for("API.display_qr_code", id=data["id"]))

        return JSONResponse(data)

    @route("/web/create", methods=["POST"])
    @limiter.limit(config["LIMITS"]["create"])  # type: ignore
    async def web_create_url(self, request: Request) -> Response:
        error_html: str = """
            <p>
                <h3 class="error validationHeader">
                    Error:
                </h3>
                {reason}
            </p>
            """

        async with request.form() as form:
            location: UploadFile | str | None = form.get("url", None)
            should_qr: UploadFile | str | bool = form.get("qrbox", False)

        try:
            validated: str = self.validate_url(location)
        except URLValidationError as e:
            reason: str = e.reason or "The provided URL is invalid or forbidden!"
            return HTMLResponse(error_html.format(reason=reason))

        payload: BasicRedirect = {"uid": None, "expiry": None, "location": validated}
        row: Redirect | None = await self.app.database.create_redirect(data=payload)
        if not row:
            return HTMLResponse(error_html.format(reason="Internal API Error... Please try again later."))

        generate_qr: bool = bool(should_qr)

        html: str = self.generate_html(request, identifier=row["id"], should_qr=generate_qr)
        return HTMLResponse(html)

    @route("/web/socials", methods=["GET"])
    async def web_socials(self, request: Request) -> Response:
        gh_url: str = config["OPTIONS"]["github_url"]
        disco_url: str = config["OPTIONS"]["discord_url"]

        html: str = f"""
            <a href="{gh_url}">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 496 512"><path fill="currentColor" d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8zM97.2 352.9c-1.3 1-1 3.3.7 5.2 1.6 1.6 3.9 2.3 5.2 1 1.3-1 1-3.3-.7-5.2-1.6-1.6-3.9-2.3-5.2-1zm-10.8-8.1c-.7 1.3.3 2.9 2.3 3.9 1.6 1 3.6.7 4.3-.7.7-1.3-.3-2.9-2.3-3.9-2-.6-3.6-.3-4.3.7zm32.4 35.6c-1.6 1.3-1 4.3 1.3 6.2 2.3 2.3 5.2 2.6 6.5 1 1.3-1.3.7-4.3-1.3-6.2-2.2-2.3-5.2-2.6-6.5-1zm-11.4-14.7c-1.6 1-1.6 3.6 0 5.9 1.6 2.3 4.3 3.3 5.6 2.3 1.6-1.3 1.6-3.9 0-6.2-1.4-2.3-4-3.3-5.6-2z"/></svg>
                GitHub
            </a>

            <a href="{disco_url}">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 512"><path fill="currentColor" d="M524.531,69.836a1.5,1.5,0,0,0-.764-.7A485.065,485.065,0,0,0,404.081,32.03a1.816,1.816,0,0,0-1.923.91,337.461,337.461,0,0,0-14.9,30.6,447.848,447.848,0,0,0-134.426,0,309.541,309.541,0,0,0-15.135-30.6,1.89,1.89,0,0,0-1.924-.91A483.689,483.689,0,0,0,116.085,69.137a1.712,1.712,0,0,0-.788.676C39.068,183.651,18.186,294.69,28.43,404.354a2.016,2.016,0,0,0,.765,1.375A487.666,487.666,0,0,0,176.02,479.918a1.9,1.9,0,0,0,2.063-.676A348.2,348.2,0,0,0,208.12,430.4a1.86,1.86,0,0,0-1.019-2.588,321.173,321.173,0,0,1-45.868-21.853,1.885,1.885,0,0,1-.185-3.126c3.082-2.309,6.166-4.711,9.109-7.137a1.819,1.819,0,0,1,1.9-.256c96.229,43.917,200.41,43.917,295.5,0a1.812,1.812,0,0,1,1.924.233c2.944,2.426,6.027,4.851,9.132,7.16a1.884,1.884,0,0,1-.162,3.126,301.407,301.407,0,0,1-45.89,21.83,1.875,1.875,0,0,0-1,2.611,391.055,391.055,0,0,0,30.014,48.815,1.864,1.864,0,0,0,2.063.7A486.048,486.048,0,0,0,610.7,405.729a1.882,1.882,0,0,0,.765-1.352C623.729,277.594,590.933,167.465,524.531,69.836ZM222.491,337.58c-28.972,0-52.844-26.587-52.844-59.239S193.056,219.1,222.491,219.1c29.665,0,53.306,26.82,52.843,59.239C275.334,310.993,251.924,337.58,222.491,337.58Zm195.38,0c-28.971,0-52.843-26.587-52.843-59.239S388.437,219.1,417.871,219.1c29.667,0,53.307,26.82,52.844,59.239C470.715,310.993,447.538,337.58,417.871,337.58Z"/></svg>
                Discord
            </a>

            <a href="/docs">
                <svg xmlns="http://www.w3.org/2000/svg" height="16" width="14" viewBox="0 0 448 512"><path fill="currentColor" d="M96 0C43 0 0 43 0 96V416c0 53 43 96 96 96H384h32c17.7 0 32-14.3 32-32s-14.3-32-32-32V384c17.7 0 32-14.3 32-32V32c0-17.7-14.3-32-32-32H384 96zm0 384H352v64H96c-17.7 0-32-14.3-32-32s14.3-32 32-32zm32-240c0-8.8 7.2-16 16-16H336c8.8 0 16 7.2 16 16s-7.2 16-16 16H144c-8.8 0-16-7.2-16-16zm16 48H336c8.8 0 16 7.2 16 16s-7.2 16-16 16H144c-8.8 0-16-7.2-16-16s7.2-16 16-16z"/></svg>
                Docs
            </a>
        """

        return HTMLResponse(html)

    @route("/qr/{id}", methods=["GET"], prefix=False)
    @limiter.limit(config["LIMITS"]["create"])  # type: ignore
    async def display_qr_code(self, request: Request) -> Response:
        identifier: str = request.path_params["id"]
        row: Redirect | None = await self.app.database.retrieve_redirect(identifier, plus=False)

        if not row:
            return Response(status_code=404)

        short: str = str(request.url_for("Redirects.redirect_base", id=identifier))
        fp: io.BytesIO = await asyncio.to_thread(self.generate_qr, short)
        return Response(fp.read(), media_type="image/png")

    @route("/stats/{id}", methods=["GET"])
    @limiter.limit(config["LIMITS"]["create"])  # type: ignore
    async def redirect_stats(self, request: Request) -> Response:
        """Create a shortened URL via API.

        ---
        summary: Retrieve basic stats for a short URL.
        description:
            Retrieve basic stats for a short URL. This includes the URL, QR code, location, expiry, ID and views.

        responses:
            200:
                description: The shortened URL data.
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                url:
                                    type: string
                                    example: https://chii.to/abc123
                                qr:
                                    type: string
                                    example: https://chii.to/qr/abc123
                                location:
                                    type: string
                                    example: https://example.com
                                expiry:
                                    type: string
                                    example: 2024-01-01T00:00:00.000000+00:00
                                id:
                                    type: string
                                    example: abc123
                                views:
                                    type: integer
                                    example: 0
            404:
                description: The URL was not found.
        """
        identifier: str = request.path_params["id"]
        row: Redirect | None = await self.app.database.retrieve_redirect(identifier, plus=False)

        if not row:
            return Response(status_code=404)

        data = dict(row)
        data.pop("uid", None)
        data["url"] = str(request.url_for("Redirects.redirect_base", id=identifier))
        data["qr"] = str(request.url_for("API.display_qr_code", id=identifier))

        return JSONResponse(data)
