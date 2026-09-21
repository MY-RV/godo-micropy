# Changelog

## [0.1.0] — 2026-09-21

### Added
- First release. Runs a script body as MicroPython inside godo's WebAssembly
  sandbox, with `godo.argv`, `godo.args`, `godo.proc.exec` and `godo.fs.slink`.
- `os.path` is frozen into the artifact alongside the shim, so paths work
  without reaching for `godo.` to join two strings.
- Built from MicroPython's WASI variant, which is
  [pull request #13676](https://github.com/micropython/micropython/pull/13676)
  and not merged upstream. `scripts/build.sh` pins it.

### Changed
- **A script body cannot import from disk.** The frozen standard library stays;
  a `.py` beside your `godo.yaml` does not. Importing half-worked — a module
  has its own globals, so `godo` was undefined inside one — and a body is a
  body, not a program. `godo.proc.exec(["python3", …])` is the way out, and
  opening this later would break nothing.
- A failed import says what the runner ships, not only what is missing.

### Fixed
- `capture=True` on a command that printed nothing gave `None` instead of `""`.
  The wire omits an empty string, so the shim fills it back in: it knows what
  it asked for.

### Notes
- The build is **not reproducible**: MicroPython embeds its build date, so two
  builds of the same source differ. A digest identifies the artifact that was
  published, not what the source produces.
- Windows is unverified. `godo.fs.slink` uses `os.Symlink`, which wants a
  junction on Windows; nobody has run this there.
