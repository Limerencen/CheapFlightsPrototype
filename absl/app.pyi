
from typing import Any, Callable, Collection, Iterable, List, NoReturn, Optional, Text, TypeVar, Union, overload

from absl.flags import _flag


_MainArgs = TypeVar('_MainArgs')
_Exc = TypeVar('_Exc', bound=Exception)


class ExceptionHandler():

  def wants(self, exc: _Exc) -> bool:
    ...

  def handle(self, exc: _Exc):
    ...


EXCEPTION_HANDLERS: List[ExceptionHandler] = ...


class HelpFlag(_flag.BooleanFlag):
  def __init__(self):
    ...


class HelpshortFlag(HelpFlag):
  ...


class HelpfullFlag(_flag.BooleanFlag):
  def __init__(self):
 