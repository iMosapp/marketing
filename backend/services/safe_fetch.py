"""Outbound fetch guard for admin-supplied URLs (site crawl, palette, inventory feeds).
Refuses loopback / private / link-local / cloud-metadata targets and re-checks every redirect hop (SSRF)."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata", "instance-data", "169.254.169.254"}
BLOCKED_SUFFIXES = (".internal", ".local", ".localhost", ".cluster", ".svc")


class UnsafeURL(ValueError):
    pass


def _ip_public(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified)


async def assert_public_url(url: str) -> None:
    p = urlparse(url)
    host = (p.hostname or "").lower().rstrip(".")
    if p.scheme not in ("http", "https") or not host:
        raise UnsafeURL("Only public http(s) addresses can be read.")
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURL("That address is not reachable from here.")
    try:
        ipaddress.ip_address(host)
        infos = [(None, None, None, None, (host, 0))]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, None)
        except socket.gaierror:
            raise UnsafeURL("That website address could not be found.")
    if not infos or not all(_ip_public(i[4][0]) for i in infos):
        raise UnsafeURL("That address is not reachable from here.")


async def _hook(request: httpx.Request) -> None:
    await assert_public_url(str(request.url))


def safe_client(**kwargs) -> httpx.AsyncClient:
    """httpx.AsyncClient that validates the first URL and every redirect target before connecting."""
    hooks = kwargs.pop("event_hooks", {}) or {}
    hooks["request"] = list(hooks.get("request", [])) + [_hook]
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)
