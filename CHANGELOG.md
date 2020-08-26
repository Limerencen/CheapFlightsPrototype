
# Python Absl Changelog

All notable changes to Python Absl are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com).

## Unreleased

### Changed

*   `absl-py` no longer supports Python 3.6. It has reached end-of-life for more
     than a year now.

## 1.4.0 (2023-01-11)

### New

*   (testing) Added `@flagsaver.as_parsed`: this allows saving/restoring flags
    using string values as if parsed from the command line and will also reflect
    other flag states after command line parsing, e.g. `.present` is set.

### Changed

*   (logging) If no log dir is specified `logging.find_log_dir()` now falls back
    to `tempfile.gettempdir()` instead of `/tmp/`.

### Fixed

*   (flags) Additional kwargs (e.g. `short_name=`) to `DEFINE_multi_enum_class`
    are now correctly passed to the underlying `Flag` object.

## 1.3.0 (2022-10-11)

### Added

*   (flags) Added a new `absl.flags.set_default` function that updates the flag
    default for a provided `FlagHolder`. This parallels the
    `absl.flags.FlagValues.set_default` interface which takes a flag name.
*   (flags) The following functions now also accept `FlagHolder` instance(s) in
    addition to flag name(s) as their first positional argument:
    -   `flags.register_validator`
    -   `flags.validator`
    -   `flags.register_multi_flags_validator`
    -   `flags.multi_flags_validator`
    -   `flags.mark_flag_as_required`
    -   `flags.mark_flags_as_required`
    -   `flags.mark_flags_as_mutual_exclusive`
    -   `flags.mark_bool_flags_as_mutual_exclusive`
    -   `flags.declare_key_flag`

### Changed

*   (testing) Assertions `assertRaisesWithPredicateMatch` and
    `assertRaisesWithLiteralMatch` now capture the raised `Exception` for
    further analysis when used as a context manager.
*   (testing) TextAndXMLTestRunner now produces time duration values with
    millisecond precision in XML test result output.
*   (flags) Keyword access to `flag_name` arguments in the following functions
    is deprecated. This parameter will be renamed in a future 2.0.0 release.
    -   `flags.register_validator`
    -   `flags.validator`
    -   `flags.register_multi_flags_validator`
    -   `flags.multi_flags_validator`
    -   `flags.mark_flag_as_required`
    -   `flags.mark_flags_as_required`
    -   `flags.mark_flags_as_mutual_exclusive`
    -   `flags.mark_bool_flags_as_mutual_exclusive`
    -   `flags.declare_key_flag`

## 1.2.0 (2022-07-18)

### Fixed

*   Fixed a crash in Python 3.11 when `TempFileCleanup.SUCCESS` is used.

## 1.1.0 (2022-06-01)

*   `Flag` instances now raise an error if used in a bool context. This prevents
    the occasional mistake of testing an instance for truthiness rather than
    testing `flag.value`.
*   `absl-py` no longer depends on `six`.

## 1.0.0 (2021-11-09)

### Changed

*   `absl-py` no longer supports Python 2.7, 3.4, 3.5. All versions have reached
    end-of-life for more than a year now.
*   New releases will be tagged as `vX.Y.Z` instead of `pypi-vX.Y.Z` in the git
    repo going forward.

## 0.15.0 (2021-10-19)

### Changed

*   (testing) #128: When running bazel with its `--test_filter=` flag, it now
    treats the filters as `unittest`'s `-k` flag in Python 3.7+.

## 0.14.1 (2021-09-30)

### Fixed

*   Top-level `LICENSE` file is now exported in bazel.

## 0.14.0 (2021-09-21)

### Fixed
