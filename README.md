# godo-micropy

Python for [GoDo](https://github.com/MY-RV/godo). A plugin that runs a script
body as MicroPython, compiled to WebAssembly, inside godo's sandbox.

```yaml
version: "0.1"

engine:
  dialect: matcher
  plugins:
    - source: ./godo-micropy.wasm
      sha256: "…"
      provides: [runner:micropy]
      config:
        proc: {exec: true}
        fs:   {mount: true, slink: true}

scripts:
  # @runner micropy
  worktree create ${BRANCH} ${DIR}: |
    import os

    branch = godo.argv["BRANCH"]
    wt = godo.argv["DIR"]

    if not os.path.isfile(".env"):
        raise Exception("no .env in the repo root; create it first")

    godo.proc.exec(["git", "worktree", "add", "-b", branch, wt])

    r = godo.proc.exec(["npm", "install"], cwd=wt, check=False)
    if not r.ok:
        print(f"warning: npm exited {r.code}, carrying on without deps")

    godo.fs.slink(".env", os.path.join(wt, ".env"))
    print(f"worktree ready: {wt} ({branch})")
```

```
$ godo worktree create wt/example ../wt-example
warning: npm exited 254, carrying on without deps
worktree ready: ../wt-example (wt/example)
```

## It is Python

Not a subset with the familiar bits filed off. Verified running inside the
artifact: `try`/`except`/`finally`, classes, f-strings with format specifiers,
comprehensions, closures, recursion, `json`, `re`, `hashlib`, and tracebacks
with the line numbers of your script body.

```
Traceback (most recent call last):
  File "<string>", line 4, in <module>
  File "<string>", line 1, in a
  File "<string>", line 2, in b
RuntimeError: from the bottom
```

## The namespace

Four things. Everything else is Python.

```python
godo.argv["BRANCH"]                  # captures from the matcher key
godo.args[0]                         # tokens left over after the match
godo.proc.exec(argv, cwd=None, capture=False, check=True)
godo.fs.slink(src, dst, force=False)
```

It is small on purpose. With `fs.mount` granted, the directory holding your
`godo.yaml` is the script's root, so Python's own library works — `os.path`,
`open()`, `os.listdir`, `os.makedirs`, `json`. Duplicating those under `godo.`
would be writing a second standard library beside the one already there.

What stays is what Python cannot answer for itself:

| | |
|---|---|
| `argv` / `args` | values godo binds at invocation; they are not in the file |
| `proc.exec` | there is no `subprocess` inside the sandbox |
| `fs.slink` | `os.symlink` is not portable — Unix wants a symlink, Windows a junction |

### Errors are values, not exceptions

`check=True` (the default) aborts the script and godo exits with the child's
exit code. `check=False` hands you the result:

```python
r = godo.proc.exec(["npm", "install"], check=False)
if not r.ok:
    ...            # r.code, r.stdout, r.stderr
```

`stdout` and `stderr` are strings when you asked for `capture=True` — including
`""` when the command printed nothing — and `None` when you did not. A captured
silence is not the same as nothing captured.

`raise` aborts with a traceback and exit 1.

## Capabilities

The sandbox starts shut. With an empty `config`, measured from inside:

```
os.listdir(".")     OSError [Errno 44] ENOENT
open("/etc/passwd") OSError [Errno 44] ENOENT
os.getenv("HOME")   None
time.time()         1640995200.0      (frozen)
import socket       the module is not there
```

`config` names what comes back, and nothing else:

| Grant | Gives |
|---|---|
| `proc.exec` | running commands |
| `fs.mount` | the directory holding your `godo.yaml`, as the script's root |
| `fs.slink` | creating symlinks |
| `time.wall` | the real clock instead of a frozen one |

`fs.slink` is not confined to the mount: a git worktree is created *beside* a
repository, and linking into it is the point. `proc.exec` can run `ln -s`
anywhere in any case, so a narrower `slink` would protect nothing. The grant is
the boundary — withhold it from a plugin you would not hand a shell.

## Preview

`godo --preview` prints the body and never starts this plugin. Your script is a
program; the only faithful answer to "what will this do" without running it is
the program itself.

## Building

Needs a WASI toolchain. On macOS:

```bash
brew install wasi-runtimes wasi-libc binaryen lld
```

`wasi-runtimes` pulls in LLVM, which is where `clang` comes from. `lld`
provides `wasm-ld`, which Homebrew's LLVM does not ship.

```bash
export WASI_SYSROOT=/opt/homebrew/opt/wasi-libc/share/wasi-sysroot
export WASI_RESOURCE_DIR=/opt/homebrew/opt/wasi-runtimes/share/wasi-runtimes
export PATH="$(brew --prefix binaryen)/bin:$(brew --prefix lld)/bin:$PATH"

./scripts/build.sh
```

The script clones MicroPython at the WASI pull request, applies the three
patches in `scripts/micropython-patches.diff`, freezes `src/godo_shim.py` and
`os.path` into the binary, and runs the binaryen passes.

Then put the printed digest in your `godo.yaml` — or let
`godo -e plugins install` do it, which is easier and cannot typo.

### The build is not reproducible

Two builds of the same source produce different bytes, and therefore different
digests. MicroPython embeds its build date in its version string.

So the digest says **"this is the artifact that was published"**, not "this is
what the source produces". You cannot verify a release by rebuilding it and
comparing. What the digest does give you is the thing that matters day to day:
everyone on a team runs the same bytes, and a change to those bytes is a change
to the file in git.

If you would rather trust your own build than a release, build it and install
from the local path. The flow is the same.

## How it works

A WASI command: a program with a `main()`, compiled to wasm. godo starts it
with no arguments, writes one JSON request to its stdin, and answers the
operations it writes back. The exit code is your script's.

`src/godo_shim.py` is frozen into the binary and boots on start. It reads the
request, builds the `godo` namespace, and executes your body. It is ordinary
Python — readable, and testable outside wasm.

Protocol: godo's [`docs/dev/plugin-protocol.md`](https://github.com/MY-RV/godo/blob/main/docs/dev/plugin-protocol.md).

## Installing

```bash
# from a release
godo -e plugins install https://github.com/MY-RV/godo-micropy/releases/download/v0.1.0/godo-micropy.wasm

# or from a local build
godo -e plugins install ./godo-micropy.wasm
```

Either writes the entry, with the digest, into your `godo.yaml`. Installing over
a plugin the catalog already declares updates that entry and **keeps its
`config`**: what a plugin may do is your decision, and install has no business
re-granting what you took away. A teammate who
clones the repository runs `godo -e plugins install` with no arguments: it
fetches what the catalog declares and refuses anything whose bytes do not match
the committed digest.

A complete catalog to copy: [`examples/godo.yaml`](./examples/godo.yaml).

## Licences

This repository is MIT. **The `.wasm` is not just MIT** — it contains
MicroPython (MIT), parts of micropython-lib (MIT plus the Python licence
stack), and wasi-libc (Apache-2.0-with-LLVM-exception, MIT, and others).

See [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md). Those notices ship
beside the artifact on every release, because the artifact is what gets
downloaded.
