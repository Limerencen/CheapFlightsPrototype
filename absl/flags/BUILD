licenses(["notice"])

py_library(
    name = "flags",
    srcs = ["__init__.py"],
    srcs_version = "PY2AND3",
    visibility = ["//visibility:public"],
    deps = [
        ":_argument_parser",
        ":_defines",
        ":_exceptions",
        ":_flag",
        ":_flagvalues",
        ":_helpers",
        ":_validators",
    ],
)

py_library(
    name = "argparse_flags",
    srcs = ["argparse_flags.py"],
    srcs_version = "PY2AND3",
    visibility = ["//visibility:public"],
    deps = [":flags"],
)

py_library(
    name = "_argument_parser",
    srcs = ["_argument_parser.py"],
    src