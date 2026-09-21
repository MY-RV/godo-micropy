# godo-micropy: the shim.
#
# Runs inside micropython.wasm. Reads godo's request from stdin, builds the
# `godo` namespace, and executes the script body.
#
# stdout carries the protocol, so a script's print() cannot go there: it would
# interleave with the ops and corrupt them. print is replaced instead, because
# MicroPython's built-in modules are read-only and sys.stdout cannot be
# reassigned.

import sys
import json

_API = 1
_raw = sys.stdout  # the protocol channel, kept before anything shadows it


def _send(obj):
    _raw.write(json.dumps(obj))
    _raw.write("\n")


def _recv():
    line = sys.stdin.readline()
    if not line:
        raise Exception("godo closed the connection")
    return json.loads(line)


def _print(*a, **k):
    """The script's print: every line leaves as an op.

    Injected into the script's globals rather than installed over sys.stdout,
    which MicroPython does not allow. A script writing to sys.stdout directly
    would still corrupt the protocol; nothing can stop that from in here.
    """
    sep = k.get("sep", " ")
    end = k.get("end", "\n")
    text = sep.join(str(x) for x in a) + end
    for line in text.split("\n")[:-1] if text.endswith("\n") else [text]:
        _send({"op": "out", "text": line})


class Argv:
    """Captures bound by the matcher key.

    Mirrors ${godo:argv[NAME]} in a shell body. Fails closed: an unbound name
    raises rather than reading as an empty string.
    """

    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        if not isinstance(k, str):
            raise TypeError("godo.argv is keyed by capture name; use godo.args for positionals")
        if k not in self._d:
            raise KeyError("capture %r was not bound by this match" % k)
        return self._d[k]

    def __contains__(self, k):
        return k in self._d

    def __len__(self):
        return len(self._d)


class Args:
    """Tokens left over after the match.

    Mirrors ${godo:args[i]}. A plugin body always accepts leftovers: it is a
    program, so what they mean is its own business.
    """

    def __init__(self, lst):
        self._l = lst

    def __getitem__(self, k):
        if isinstance(k, str):
            raise TypeError("godo.args is positional; use godo.argv for captures")
        return self._l[k]

    def __len__(self):
        return len(self._l)

    def __iter__(self):
        return iter(self._l)


class Result:
    """What a command did. Errors are values here, not exceptions.

    stdout and stderr are strings when capture was asked for and None when it
    was not — including when the command printed nothing. The wire omits an
    empty string, so the side that knows what it asked for fills it back in;
    a captured silence is "" and must not read as "nothing was captured".
    """

    def __init__(self, d, capture):
        self.code = d.get("code", 0)
        self.ok = d.get("ok", False)
        self.stdout = d.get("stdout", "") if capture else None
        self.stderr = d.get("stderr", "") if capture else None


class Proc:
    def exec(self, argv, cwd=None, capture=False, check=True):
        """Run a command and wait.

        check=True (the default) aborts the script on a non-zero exit, and godo
        leaves with the child's code. check=False hands back the Result so the
        script can decide — which is what replaces try/except for commands.

        Needs config.proc.exec.
        """
        op = {"op": "exec", "argv": list(argv)}
        if cwd:
            op["dir"] = cwd
        if capture:
            op["capture"] = True
        _send(op)
        d = _recv()
        if d.get("error"):
            raise Exception(d["error"])
        r = Result(d, capture)
        if check and not r.ok:
            sys.exit(r.code)
        return r


class Response:
    """An HTTP response. A status is a value, not an exception.

    The body arrives base64-encoded because it is bytes: carrying it as a JSON
    string would replace anything that is not valid UTF-8, and an image would
    come out shorter than it left with nothing raised.
    """

    def __init__(self, d):
        import binascii

        self.status = d.get("code", 0)
        self.ok = d.get("ok", False)
        self.headers = d.get("headers") or {}
        self.content = binascii.a2b_base64(d.get("base64", ""))

    @property
    def text(self):
        return self.content.decode()

    def json(self):
        import json as _json

        return _json.loads(self.text)


class Net:
    """The network, reached through godo.

    A wasm guest has no sockets, so this is not a convenience over `socket` —
    it is the only way out. Going through godo rather than exec'ing curl is the
    difference between a script that runs anywhere and one that runs wherever
    somebody happened to install a tool.

    Named net rather than http because that is the shape of the thing: if a
    socket ever arrives it belongs here, not beside here.
    """

    def request(self, method, url, headers=None, body=None, check=False, timeout=None):
        op = {"op": "fetch", "url": url, "method": method}
        if headers:
            op["headers"] = headers
        if body is not None:
            op["body"] = body
        if timeout:
            op["timeout"] = int(timeout)
        _send(op)
        d = _recv()
        if d.get("error"):
            raise Exception(d["error"])
        r = Response(d)
        if check and not r.ok:
            raise Exception("%s %s -> %d" % (method, url, r.status))
        return r

    def get(self, url, headers=None, check=False, timeout=None):
        return self.request("GET", url, headers, None, check, timeout)

    def post(self, url, body=None, headers=None, check=False, timeout=None):
        return self.request("POST", url, headers, body, check, timeout)


class Fs:
    def slink(self, src, dst, force=False):
        """Link src to dst: a symlink on Unix, a junction on Windows.

        The one filesystem operation a mounted directory does not solve, since
        os.symlink is not portable. Everything else — paths, reading, writing,
        listing — is Python's own library.

        Needs config.fs.slink. Windows is unverified.
        """
        _send({"op": "slink", "src": src, "dst": dst, "force": bool(force)})
        d = _recv()
        if d.get("error"):
            raise Exception(d["error"])


class Godo:
    def __init__(self, req):
        self.argv = Argv(req.get("argv") or {})
        self.args = Args(req.get("args") or [])
        self.proc = Proc()
        self.fs = Fs()
        self.net = Net()
        self.runner = req.get("runner", "")


# What this runner ships. Named so a failed import can say what is here
# instead of only what is not.
_AVAILABLE = "os, os.path, json, re, sys, io, time, collections, hashlib, binascii, struct"


def _seal_imports():
    """Leave the frozen stdlib importable and take the filesystem away.

    A .godo.py is a script body, not a Python program — the way a Dockerfile
    does not invoke another Dockerfile. Importing from disk half-works anyway:
    a module gets its own globals, so `godo` is not defined there, and the
    failure arrives in the middle of a run instead of at the top.

    Closing it is the reversible direction. Opening it later breaks nothing;
    taking it back once people have module trees is not possible. When a script
    genuinely needs a program, it stays a program:

        godo.proc.exec(["python3", "scripts/thing.py"])
    """
    sys.path.clear()
    sys.path.append(".frozen")


def _import_error(e):
    """Say what is available, not only what is missing."""
    name = str(e).split("'")[1] if "'" in str(e) else "?"
    sys.stderr.write(
        "ImportError: no module named '%s'\n"
        "  godo-micropy ships: %s\n"
        "  A script body cannot import from disk. For code that needs to, run\n"
        "  it as a program: godo.proc.exec([\"python3\", \"path/to/it.py\"])\n"
        % (name, _AVAILABLE)
    )


def main():
    req = _recv()
    if req.get("api") != _API:
        sys.stderr.write(
            "godo-micropy speaks api %d, godo speaks %s\n" % (_API, req.get("api"))
        )
        sys.exit(1)

    godo = Godo(req)
    _seal_imports()
    g = {"godo": godo, "print": _print, "__name__": "__main__"}
    try:
        exec(req.get("body", ""), g)
    except SystemExit:
        raise
    except ImportError as e:
        _import_error(e)
        sys.exit(1)
    except Exception as e:
        # Explicit: MicroPython's print_exception writes to stdout by default,
        # and stdout is the protocol. The traceback belongs on stderr, which
        # godo passes through untouched.
        sys.print_exception(e, sys.stderr)
        sys.exit(1)
    sys.exit(0)


main()
