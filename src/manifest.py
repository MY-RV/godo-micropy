# Frozen into the godo-micropy artifact.
#
# os.path is not in the MicroPython core; it comes from micropython-lib. It is
# frozen in rather than left out because a script that cannot join a path is
# not a script anyone wants to write.
require("os-path")

# The shim: reads godo's request from stdin and exposes the godo namespace.
module("godo_shim.py", base_path="frozen")
