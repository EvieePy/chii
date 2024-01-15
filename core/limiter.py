from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import config


limiter: Limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    default_limits=config["LIMITS"]["globals"],  # type: ignore
)
