# Changelog

## [Unreleased]

### Added
- First release. Runs a script body as MicroPython inside godo's WebAssembly
  sandbox, with `godo.argv`, `godo.args`, `godo.proc.exec` and `godo.fs.slink`.
- `os.path` is frozen into the artifact alongside the shim, so paths work
  without reaching for `godo.` to join two strings.
- Built from MicroPython's WASI variant, which is
  [pull request #13676](https://github.com/micropython/micropython/pull/13676)
  and not merged upstream. `scripts/build.sh` pins it.

### Notes
- The build is **not reproducible**: MicroPython embeds its build date, so two
  builds of the same source differ. A digest identifies the artifact that was
  published, not what the source produces.
- Windows is unverified. `godo.fs.slink` uses `os.Symlink`, which wants a
  junction on Windows; nobody has run this there.
