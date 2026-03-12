"""Cookie parsing and construction utilities using stdlib http.cookies.

Cookie parsing and set-cookie header construction using
zero-dependency stdlib equivalents.

References:
    FR-049: Set-Cookie header construction
    FR-050: Cookie header parsing
    R5: stdlib SimpleCookie decision
"""

from http.cookies import SimpleCookie


def parse_cookies(event: dict) -> dict[str, str]:
    """Parse the Cookie header from an API Gateway event.

    Args:
        event: API Gateway Proxy Integration event dict.

    Returns:
        Dict mapping cookie names to values. Empty dict if no cookies.
    """
    headers = event.get("headers") or {}
    cookie_header = headers.get("cookie", "")
    if not cookie_header:
        return {}
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    return {k: v.value for k, v in cookie.items()}


def make_set_cookie(
    name: str,
    value: str,
    *,
    httponly: bool = True,
    secure: bool = True,
    samesite: str = "Lax",
    max_age: int = 3600,
    path: str = "/",
) -> str:
    """Construct a Set-Cookie header value.

    Args:
        name: Cookie name.
        value: Cookie value.
        httponly: Whether to set HttpOnly flag.
        secure: Whether to set Secure flag.
        samesite: SameSite attribute ("Strict", "Lax", or "None").
        max_age: Max-Age in seconds.
        path: Cookie path.

    Returns:
        Complete Set-Cookie header value string.
    """
    cookie = SimpleCookie()
    cookie[name] = value
    cookie[name]["httponly"] = httponly
    cookie[name]["secure"] = secure
    cookie[name]["samesite"] = samesite
    cookie[name]["max-age"] = max_age
    cookie[name]["path"] = path
    return cookie[name].OutputString()
