#!/usr/bin/env bash
# Builds godo-micropy.wasm: MicroPython for WASI with the godo shim frozen in.
#
# The artifact is a WASI command. godo starts it with no arguments and speaks
# JSON over its stdin and stdout; see godo's docs/dev/plugin-protocol.md.
set -euo pipefail

MP_REF="${MP_REF:-pull/13676/head}"   # WASI support is still a PR upstream
OUT="${OUT:-$PWD/godo-micropy.wasm}"
WORK="${WORK:-$(mktemp -d)}"
HERE="$(cd "$(dirname "$0")" && pwd)"

for t in clang wasm-opt wasm-ld; do
  command -v "$t" >/dev/null || { echo "missing: $t — see README" >&2; exit 1; }
done

LLVM="$(dirname "$(dirname "$(command -v clang)")")"
SYSROOT="${WASI_SYSROOT:?set WASI_SYSROOT}"
RESOURCES="${WASI_RESOURCE_DIR:?set WASI_RESOURCE_DIR}"

git clone -q --depth 1 https://github.com/micropython/micropython.git "$WORK/mp"
cd "$WORK/mp"
git fetch -q --depth 1 origin "$MP_REF:build"
git checkout -q build

# Three patches, each explained in scripts/micropython-patches.diff:
#  - the variant's target triple, which clang 23 no longer accepts as wasm32-wasi
#  - a -Werror that stops MicroPython building under a modern clang
#  - a boot hook, because stdin carries godo's protocol and cannot be a script
git apply "$HERE/micropython-patches.diff"

mkdir -p ports/unix/variants/wasi/frozen
cp "$HERE/../src/godo_shim.py" ports/unix/variants/wasi/frozen/
cp "$HERE/../src/manifest.py" ports/unix/variants/wasi/

make -C mpy-cross -j"$(getconf _NPROCESSORS_ONLN)" CFLAGS_EXTRA="-Wno-gnu-folding-constant"
make -C ports/unix submodules

make -C ports/unix VARIANT=wasi -j"$(getconf _NPROCESSORS_ONLN)" \
  WASI_SDK="$LLVM" \
  WASI_SYSROOT="$SYSROOT" \
  RESOURCE_DIR="$RESOURCES" \
  STRIP= \
  SIZE="$LLVM/bin/llvm-size" \
  FROZEN_MANIFEST=variants/wasi/manifest.py \
  CFLAGS_EXTRA="-Wno-gnu-folding-constant" \
  LDFLAGS_EXTRA="-B $(dirname "$(command -v wasm-ld)")/ -Wl,--export=__stack_pointer"

# Never --all-features here: it enables memory64, which re-encodes imports with
# 64-bit indices and makes wazero reject the module outright. Name the features
# the artifact actually uses — which is also what it should declare.
F=(--enable-mutable-globals --enable-bulk-memory --enable-bulk-memory-opt
   --enable-sign-ext --enable-exception-handling --enable-reference-types
   --enable-multivalue --enable-nontrapping-float-to-int)

BIN=ports/unix/build-wasi/micropython
wasm-opt "${F[@]}" --spill-pointers      -o "$WORK/a.wasm" "$BIN"
wasm-opt "${F[@]}" --translate-to-exnref -o "$WORK/b.wasm" "$WORK/a.wasm"
wasm-opt "${F[@]}" -Oz                   -o "$OUT"          "$WORK/b.wasm"

echo "built: $OUT"
shasum -a 256 "$OUT"
