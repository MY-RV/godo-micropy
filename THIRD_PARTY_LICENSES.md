# Third-party licenses

This repository's own code — the shim in `src/`, the build script, the
patches — is MIT (see [LICENSE](./LICENSE)).

**`godo-micropy.wasm` is not.** It is a compiled artifact containing the
projects below, and their notices travel with it: they are published beside the
`.wasm` on every release, because the artifact is what people download.

Every licence here is permissive. None of them is copyleft, and none asks this
repository to change its own.

---

## MicroPython

The interpreter. Built from
[`micropython/micropython`](https://github.com/micropython/micropython), the
WASI variant from pull request
[#13676](https://github.com/micropython/micropython/pull/13676) — WASI support
is not yet merged upstream.

MIT License, `Copyright (c) 2013-2026 Damien P. George`.

Full text: [`micropython/LICENSE`](https://github.com/micropython/micropython/blob/master/LICENSE).

## micropython-lib

`os.path` is frozen into the artifact and comes from
[`micropython/micropython-lib`](https://github.com/micropython/micropython-lib).

**Multi-licensed.** MIT for the library's own code, plus the Python licence
stack for the parts derived from CPython's standard library:

| | |
|---|---|
| MIT | `Copyright (c) 2013, 2014 micropython-lib contributors` |
| Python Software Foundation License v2 | `Copyright (c) 2001-2013 Python Software Foundation` |
| BeOpen Python Open Source License v1 | |
| CNRI License Agreement for Python 1.6.1 | `Copyright (c) 1995-2001 Corporation for National Research Initiatives` |
| CWI License Agreement (Python 0.9.0-1.2) | `Copyright (c) 1991-1995 Stichting Mathematisch Centrum, Amsterdam` |

Full text: [`micropython-lib/LICENSE`](https://github.com/micropython/micropython-lib/blob/master/LICENSE).

## wasi-libc

Statically linked into the artifact at build time. From
[`WebAssembly/wasi-libc`](https://github.com/WebAssembly/wasi-libc).

Multi-licensed under **Apache License 2.0 with LLVM Exception**, **Apache
License 2.0**, and **MIT**. It also carries third-party components:

| Component | |
|---|---|
| `dlmalloc/` | CC0 |
| `emmalloc/` | MIT |
| `libc-bottom-half/cloudlibc/` | BSD-2-Clause |
| `libc-top-half/musl/` | MIT |
| `fts/musl-fts/` | BSD-3-Clause |

Full text: [`wasi-libc/LICENSE`](https://github.com/WebAssembly/wasi-libc/blob/main/LICENSE).

---

## Not included

`godo` itself is a separate program under its own MIT licence. It loads this
artifact; it does not contain it, and this repository does not contain godo.
