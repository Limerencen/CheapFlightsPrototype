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
    srcs_version = "PY2AND3",
    deps = [
        ":_helpers",
    ],
)

py_library(
    name = "_defines",
    srcs = ["_defines.py"],
    srcs_version = "PY2AND3",
    deps = [
        ":_argument_parser",
        ":_exceptions",
        ":_flag",
        ":_flagvalues",
        ":_helpers",
        ":_validators",
    ],
)

py_library(
    name = "_exceptions",
    srcs = ["_exceptions.py"],
    srcs_version = "PY2AND3",
    deps = [
        ":_helpers",
    ],
)

py_library(
    name = "_flag",
    srcs = ["_flag.py"],
    srcs_version = "PY2AND3",
    deps = [
        ":_argument_parser",
        ":_exceptions",
        ":_helpers",
    ],
)

py_library(
    name = "_flagvalues",
    srcs = ["_flagvalues.py"],
    srcs_version = "PY2AND3",
    deps = [
        ":_exceptions",
        ":_flag",
        ":_helpers",
        ":_validators_classes",
    ],
)

py_library(
    name = "_helpers",
    srcs = ["_helpers.py"],
    srcs_version = "PY2AND3",
)

py_library(
    name = "_validators",
    srcs = [
        "_validators.py",
    ],
    srcs_version = "PY2AND3",
    deps = [
        ":_exceptions",
        ":_flagvalues",
        ":_validators_classes",
    ],
)

py_library(
    name = "_validators_classes",
    srcs = [
        "_validators_classes.py",
    ],
    srcs_version = "PY2AND3",
    deps = [
        ":_exceptions",
    ],
)

py_test(
    name = "tests/_argu