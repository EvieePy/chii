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
import asyncio
import logging

import uvicorn

import core
import server
from database import Database


config = core.config

try:
    LEVEL: int = int(config["LOGGING"]["level"])
except Exception:
    core.setup_logging(level=logging.INFO)
else:
    core.setup_logging(level=LEVEL)


async def main() -> None:
    async with Database() as db, server.Server(database=db) as app:
        uvconfig: uvicorn.Config = uvicorn.Config(app=app, host=config["SERVER"]["host"], port=config["SERVER"]["port"])
        uvserver: uvicorn.Server = uvicorn.Server(config=uvconfig)

        await uvserver.serve()


asyncio.run(main())
