package(default_visibility = ["//visibility:public"])

load("@rules_python//python:defs.bzl", "py_binary", "py_library")

py_library(
    name = "compiler",
    srcs = glob(["compiler/**/*.py"]),
    deps = [
        "@pip//lark",
        "@pip//llvmlite",
    ],
)

py_binary(
    name = "sinterc",
    srcs = ["compiler/main.py"],
    main = "compiler/main.py",
    deps = [":compiler"],
)
