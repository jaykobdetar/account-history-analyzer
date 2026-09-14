#!/usr/bin/env python3
"""Execute a process under an inherited Linux seccomp network-denial filter.

Blocks socket creation, connections and datagram sends at the kernel, including
child processes and native numerical libraries. Fails closed if unavailable.
"""
import ctypes
import ctypes.util
import errno
import os
import sys


def install() -> None:
    path = ctypes.util.find_library('seccomp')
    if not path:
        raise RuntimeError('libseccomp required for the offline reference runner')
    lib = ctypes.CDLL(path, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise RuntimeError('seccomp_init failed')
    try:
        for name in ('socket', 'socketpair', 'connect', 'sendto', 'sendmsg', 'sendmmsg', 'io_uring_setup'):
            nr = lib.seccomp_syscall_resolve_name(name.encode())
            if nr >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, nr, 0) != 0:
                raise RuntimeError(f'seccomp rule failed: {name}')
        if lib.seccomp_load(ctx) != 0:
            raise RuntimeError('seccomp_load failed')
    finally:
        lib.seccomp_release(ctx)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: offline_exec.py COMMAND [ARG ...]')
    install()
    import socket
    try:
        socket.socket()
    except PermissionError:
        pass
    else:
        raise RuntimeError('network denial self-check failed')
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      AHAS_NETWORK_ISOLATION='linux_seccomp_socket_denial')
    os.execvp(sys.argv[1], sys.argv[1:])
