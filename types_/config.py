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
from typing import TypedDict


class ServerConfig(TypedDict):
    host: str
    port: int


class DatabaseConfig(TypedDict):
    dsn: str


class LoggingConfig(TypedDict):
    level: int


class OptionsConfig(TypedDict):
    enable_signups: bool


class ConfigType(TypedDict):
    SERVER: ServerConfig
    DATABASE: DatabaseConfig
    LOGGING: LoggingConfig
