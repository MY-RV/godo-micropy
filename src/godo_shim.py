# godo-micropy: el shim.
#
# Corre dentro de micropython.wasm. Lee la peticion de godo por stdin, arma el
# objeto `godo`, y ejecuta el cuerpo del script.
#
# stdout es el canal del protocolo, asi que sys.stdout se reemplaza: lo que el
# script imprima viaja como un op, no se mezcla con los ops de godo.

import sys
import json

_API = 1
_raw = sys.stdout          # el canal del protocolo, antes de reemplazarlo


def _send(obj):
    _raw.write(json.dumps(obj))
    _raw.write("\n")


def _recv():
    line = sys.stdin.readline()
    if not line:
        raise Exception("godo cerro la conexion")
    return json.loads(line)


def _print(*a, **k):
    """El print del script: cada linea sale como un op.

    MicroPython no deja reasignar sys.stdout (los modulos built-in son de solo
    lectura), asi que se inyecta este print en los globals del script. stdout
    queda intacto para el protocolo.
    """
    sep = k.get("sep", " ")
    end = k.get("end", "\n")
    text = sep.join(str(x) for x in a) + end
    for line in text.split("\n")[:-1] if text.endswith("\n") else [text]:
        _send({"op": "out", "text": line})


class Argv:
    """Captures de la key del matcher."""

    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        if not isinstance(k, str):
            raise TypeError("godo.argv se indexa por nombre; usa godo.args para posicionales")
        if k not in self._d:
            raise KeyError("capture %r no ligado por el match" % k)
        return self._d[k]

    def __contains__(self, k):
        return k in self._d

    def __len__(self):
        return len(self._d)


class Args:
    """Tokens sobrantes tras el match."""

    def __init__(self, lst):
        self._l = lst

    def __getitem__(self, k):
        if isinstance(k, str):
            raise TypeError("godo.args es posicional; usa godo.argv para captures")
        return self._l[k]

    def __len__(self):
        return len(self._l)

    def __iter__(self):
        return iter(self._l)


class Result:
    def __init__(self, d):
        self.code = d.get("code", 0)
        self.ok = d.get("ok", False)
        self.stdout = d.get("stdout")
        self.stderr = d.get("stderr")


class Proc:
    def exec(self, argv, cwd=None, capture=False, check=True):
        op = {"op": "exec", "argv": list(argv)}
        if cwd:
            op["dir"] = cwd
        if capture:
            op["capture"] = True
        _send(op)
        d = _recv()
        if d.get("error"):
            raise Exception(d["error"])
        r = Result(d)
        if check and not r.ok:
            sys.exit(r.code)
        return r


class Fs:
    def slink(self, src, dst, force=False):
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
        self.runner = req.get("runner", "")


def main():
    req = _recv()
    if req.get("api") != _API:
        sys.stderr.write("godo-micropy habla api %d, godo habla %s\n" % (_API, req.get("api")))
        sys.exit(1)

    godo = Godo(req)
    g = {"godo": godo, "print": _print, "__name__": "__main__"}
    try:
        exec(req.get("body", ""), g)
    except SystemExit:
        raise
    except Exception as e:
        # Explicito: print_exception de MicroPython escribe a stdout por
        # defecto, y stdout es el canal del protocolo. El traceback va a
        # stderr, que godo pasa tal cual.
        sys.print_exception(e, sys.stderr)
        sys.exit(1)
    sys.exit(0)


main()
