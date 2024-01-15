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
import logging
import re
import secrets
import string
from typing import TYPE_CHECKING, Any, Self, cast

import asyncpg

import core
from types_ import Redirect


if TYPE_CHECKING:
    from types_ import BasicRedirect

    _Pool = asyncpg.Pool[asyncpg.Record]
else:
    _Pool = asyncpg.Pool


logger: logging.Logger = logging.getLogger(__name__)

EMAIL_VALIDATE: re.Pattern[str] = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
ALPHABET: str = string.ascii_letters + string.digits


class Database:
    pool: _Pool

    async def __aenter__(self) -> Self:
        await self.setup()
        return self

    async def __aexit__(self, *args: Any) -> None:
        try:
            await asyncio.wait_for(self.pool.close(), 10)
        except TimeoutError:
            logger.warning("Database was closed but timed-out trying to gracefully shutdown.")
        except Exception as e:
            logger.debug("Database encountered an error shutting down: %s.", e)

    async def setup(self) -> Self:
        pool: _Pool | None = await asyncpg.create_pool(dsn=core.config["DATABASE"]["dsn"])

        if pool is None:
            raise RuntimeError("Unable to create a Database Connection Pool.")

        with open("SCHEMA.sql") as fp:
            await pool.execute(fp.read())

        self.pool = pool
        await self._initial_user()

        logger.info("Successfully started Database.")

        return self

    async def _initial_user(self) -> None:
        async with self.pool.acquire() as connection:
            count: int = await connection.fetchval("""SELECT count(*) FROM users""")

            if count > 0:
                return

            # This logging setup/call is intentional...
            _log: logging.Logger = logging.getLogger("__ADMIN_CREATION__")
            _log.critical(
                (
                    "\n\nPlease read and confirm to the following!!!"
                    "\n\nThe users table is empty and needs an ADMIN ACCOUNT.\n"
                    "The default admin account can not be logged into via the web interface.\n"
                    "You are provided with your admin token now, store this in a secure place and do not share it.\n\n"
                    "DO NOT use this token to make API calls. Please create a user level account!\n\n"
                )
            )

            accept: str = input("\n\nPlease confirm (y/N): ").lower()

            if accept not in ("y", "yes"):
                raise RuntimeError("Unable to initialise the ADMIN ACCOUNT as you did not confirm.")

            token: str = secrets.token_urlsafe(128)

            query: str = """
            INSERT INTO users(email, moderator, token)
            VALUES($1, $2, $3)
            """
            async with self.pool.acquire() as connection:
                await connection.execute(query, "__ADMIN__", True, token)

            print(f"\n\n----START ADMIN ACCOUNT TOKEN----\n\n{token}\n\n----END ADMIN ACCOUNT TOKEN------\n\n")
            logger.info("Successfully created the ADMIN ACCOUNT.")

    async def create_redirect(self, data: BasicRedirect) -> Redirect | None:
        query: str = """
        INSERT INTO redirects(id, uid, expiry, location) VALUES($1, $2, $3, $4) RETURNING *
        """
        identifier: str = "".join(secrets.choice(ALPHABET) for _ in range(8))
        async with self.pool.acquire() as connection:
            row: asyncpg.Record | None = await connection.fetchrow(
                query, identifier, data["uid"], data["expiry"], data["location"]
            )

        if not row:
            return

        response: Redirect = cast(Redirect, row)
        return response

    async def retrieve_redirect(self, identifier: str, *, plus: bool = False) -> Redirect | None:
        query: str
        if plus:
            query = """
            UPDATE redirects
            SET views = views + 1
            WHERE id = $1
            RETURNING *
            """
        else:
            query = """SELECT * FROM redirects WHERE id = $1"""

        async with self.pool.acquire() as connection:
            row: asyncpg.Record | None = await connection.fetchrow(query, identifier)

        if not row:
            return

        response: Redirect = cast(Redirect, row)
        return response
