"""MIT License

Copyright (c) 2023 PythonistaGuild

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Literal, Self

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .limiter import RateLimit, Store


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from starlette.types import Receive, Scope, Send

    from types_ import ExemptCallable, LimitDecorator, RateLimitData, ResponseType, T_LimitDecorator


__all__ = (
    "route",
    "limit",
    "View",
    "Application",
    "WebsocketCloseCodes",
    "WebsocketOPCodes",
    "WebsocketSubscriptions",
    "WebsocketNotificationTypes",
)


class _Route:
    def __init__(self, **kwargs: Any) -> None:
        self._path: str = kwargs["path"]
        self._coro: Callable[[Any, Request], ResponseType] = kwargs["coro"]
        self._methods: list[str] = kwargs["methods"]
        self._prefix: bool = kwargs["prefix"]
        self._limits: RateLimitData = kwargs.get("limits", {})

        self._view: View | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        ip: str = request.headers.get("X-Forwarded-For", None) or request.client.host  # type: ignore

        exempt: ExemptCallable = self._limits.get("exempt", None)
        if exempt is not None and await exempt(request):
            pass

        elif self._limits and ip not in ("127.0.0.1", "::1"):
            limit: RateLimit = RateLimit(self._limits["rate"], self._limits["per"])  # TODO: Buckets...
            key: str = f"{ip}@{self._path}"

            if retry := Store.update(key, limit):
                response = JSONResponse(
                    {"error": "You are requesting too fast. Slow down!"},
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )
                await response(scope, receive, send)
                return

        response = await self._coro(self._view, request)
        await response(scope, receive, send)


def route(path: str, /, *, methods: list[str] = ["GET"], prefix: bool = True) -> Callable[..., _Route]:
    """Decorator which allows a coroutine to be turned into a `starlette.routing.Route` inside a `core.View`.

    Parameters
    ----------
    path: str
        The path to this route. By default, the path is prefixed with the View class name.
    methods: list[str]
        The allowed methods for this route. Defaults to ``['GET']``.
    prefix: bool
        Whether the route path should be prefixed with the View class name. Defaults to True.
    """

    def decorator(coro: Callable[[Any, Request], ResponseType]) -> _Route:
        if not asyncio.iscoroutinefunction(coro):
            raise RuntimeError("Route callback must be a coroutine function.")

        disallowed: list[str] = ["get", "post", "put", "patch", "delete", "options"]
        if coro.__name__.lower() in disallowed:
            raise ValueError(f'Route callback function must not be named any: {", ".join(disallowed)}')

        limits: RateLimitData = getattr(coro, "__limits__", {})  # type: ignore
        return _Route(path=path, coro=coro, methods=methods, prefix=prefix, limits=limits)

    return decorator


def limit(
    rate: int, per: int, *, bucket: Literal["ip", "user"] = "ip", exempt: ExemptCallable = None
) -> T_LimitDecorator:
    """Decorator which allows a Route to have a rate limit.

    Rate limits use the GCRA algorithm and are stored in memory.

    Parameters
    ----------
    rate: int
        The number of requests allowed per period.
    per: int
        The period in seconds.
    bucket: Literal["ip", "user"]
        The bucket to use for rate limiting. Defaults to "ip".
    exempt: Optional[ExemptCallable]
        An awaitable which takes a `starlette.requests.Request` and returns a boolean. If this returns True, the rate
        limit is not applied. Defaults to None.
    """

    def decorator(coro: Callable[[Any, Request], ResponseType] | _Route) -> LimitDecorator:
        limits: RateLimitData = {"rate": rate, "per": per, "bucket": bucket, "exempt": exempt}

        if isinstance(coro, _Route):
            coro._limits = limits
        else:
            setattr(coro, "__limits__", limits)

        return coro

    return decorator


class View:
    """Class based view for Starlette which allows use of the `core.route` decorator.

    All methods decorated with `core.route` are eventually turned into `starlette.routing.Route` which can be added to
    a Starlette app as a route.

    All decorated routes will have their path prefixed with the class name by default. Set `prefix=False`
    in the decorator to disable this.

    For example:

        class Stuff(View):

            @route('/hello', methods=['GET'])
            async def hello_endpoint(self, request: Request) -> Response:
                return Response(status_code=200)

        # The above View 'Stuff' has a route '/hello'. Since prefix=True by default, the full path to this route
        # is '/stuff/hello'.

    Calling `list()` on a view instance will return a list of the `starlette.routing.Route`'s in this instance.
    """

    __routes__: list[Route]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls)
        name = cls.__name__

        self.__routes__ = []

        for _, member in inspect.getmembers(self, predicate=lambda m: isinstance(m, _Route)):
            member._view = self
            path: str = member._path

            if member._prefix:
                path = f'/{name.lower()}/{path.lstrip("/")}'

            for method in member._methods:
                method = method.lower()

                # Due to the way Starlette works, this allows us to have schema documentation...
                setattr(member, method, member._coro)

            new: Route = Route(
                path=path, endpoint=member, methods=member._methods, name=f"{name}.{member._coro.__name__}"
            )
            new.limits = getattr(member, "_limits", {})  # type: ignore

            self.__routes__.append(new)

        return self

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    def __repr__(self) -> str:
        return f"View: name={self.__class__.__name__}, routes={self.__routes__}"

    def __getitem__(self, index: int) -> Route:
        return self.__routes__[index]

    def __len__(self) -> int:
        return len(self.__routes__)

    def __iter__(self) -> Iterator[Route]:
        return iter(self.__routes__)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, View):
            return False

        return self.name == other.name


class Application(Starlette):
    """The main Application which inherits from `starlette.applications.Starlette`.

    Parameters
    ----------
    prefix: Optional[str]
        The base path prefix to add to all view based routes.
    views: Optional[list[View]]
        The views to add to this Application.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._views: list[View] = []
        self._prefix: str = kwargs.pop("prefix", "")
        views: list[View] = kwargs.pop("views", [])

        super().__init__(*args, **kwargs)  # type: ignore

        for view in views:
            self.add_view(view)

    @property
    def prefix(self) -> str:
        """Returns the Application path prefix if set.

        This can not be set after initialisation.
        """
        return self._prefix

    @property
    def views(self) -> list[View]:
        """Returns a list of the currently added views on this Application.

        This can not be set after initialisation.
        """
        return self._views

    def add_view(self, view: View) -> None:
        """Adds a `core.View` and all it's routes to the Application.

        Each view must have a unique name.
        """
        if view in self._views:
            msg: str = f'A view with the name "{view.name}" has already been added to this application.'
            raise RuntimeError(msg)

        for route_ in view:
            path = f'/{self._prefix.lstrip("/")}{route_.path}' if self._prefix else route_.path
            new = Route(path, endpoint=route_.endpoint, methods=route_.methods, name=route_.name)  # type: ignore
            new.limits = route_.limits  # type: ignore

            self.router.routes.append(new)

        self._views.append(view)


class WebsocketCloseCodes:
    NORMAL: int = 1000
    ABNORMAL: int = 1006


class WebsocketOPCodes:
    # Sent...
    HELLO: int = 0
    EVENT: int = 1
    NOTIFICATION: int = 2

    # Received...
    SUBSCRIBE: str = "subscribe"
    UNSUBSCRIBE: str = "unsubscribe"


class WebsocketSubscriptions:
    DPY_MOD_LOG: str = "dpy_modlog"


class WebsocketNotificationTypes:
    # Subscriptions...
    SUBSCRIPTION_ADDED: str = "subscription_added"
    SUBSCRIPTION_REMOVED: str = "subscription_removed"

    # Failures...
    UNKNOWN_OP: str = "unknown_op"
