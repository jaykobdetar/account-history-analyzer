#!/usr/bin/env python3
"""Run browser inspection with Unix IPC permitted and network sockets denied.

Unlike the analyzer's stricter runner, Chrome needs Unix-domain socket IPC. This
Linux seccomp profile denies socket/socketpair domains other than AF_UNIX and
io_uring/socketcall bypasses. Existing non-Unix socket descriptors are closed.
"""
import ctypes
import ctypes.util
import errno
import os
import socket
import sys


class ArgumentComparison(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def install() -> None:
    for entry in os.listdir("/proc/self/fd"):
        fd = int(entry)
        try:
            inherited = socket.socket(fileno=fd)
        except OSError:
            continue
        if inherited.family != socket.AF_UNIX:
            inherited.close()
        else:
            inherited.detach()
    location = ctypes.util.find_library("seccomp")
    if not location:
        raise RuntimeError("libseccomp required for browser network isolation")
    library = ctypes.CDLL(location, use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ArgumentComparison)]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7fff0000)
    if not context:
        raise RuntimeError("seccomp_init failed")
    try:
        for name in ("socket", "socketpair", "socketcall", "io_uring_setup"):
            syscall = library.seccomp_syscall_resolve_name(name.encode("ascii"))
            if syscall < 0:
                continue
            # SCMP_CMP_NE: syscall argument 0 (domain) differs from AF_UNIX.
            comparison = ArgumentComparison(0, 1, socket.AF_UNIX, 0)
            conditional = name in {"socket", "socketpair"}
            if library.seccomp_rule_add_array(context, 0x00050000 | errno.EPERM, syscall,
                                             1 if conditional else 0,
                                             ctypes.byref(comparison) if conditional else None) != 0:
                raise RuntimeError(f"seccomp rule failed: {name}")
        if library.seccomp_load(context) != 0:
            raise RuntimeError("seccomp_load failed")
    finally:
        library.seccomp_release(context)
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.socket(family)
        except PermissionError:
            pass
        else:
            raise RuntimeError("Browser network isolation self-check failed")
    left, right = socket.socketpair()
    left.close()
    right.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: browser_offline_exec.py COMMAND [ARG ...]")
    install()
    os.environ["AHAS_BROWSER_NETWORK_ISOLATION"] = "linux_seccomp_nonunix_socket_denial"
    os.execvp(sys.argv[1], sys.argv[1:])
