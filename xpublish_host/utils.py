import itertools
import types
import weakref
from typing import (
    Generic,
    List,
    TypeVar,
)

from pydantic import conlist


class TypeParametersMemoizer(type):
    """
    https://github.com/tiangolo/fastapi/discussions/8225#discussioncomment-5149945
    """
    _generics_cache = weakref.WeakValueDictionary()

    def __getitem__(cls, typeparams):

        # prevent duplication of generic types
        if typeparams in cls._generics_cache:
            return cls._generics_cache[typeparams]

        # middleware class for holding type parameters
        class TypeParamsWrapper(cls):
            __type_parameters__ = typeparams if isinstance(typeparams, tuple) else (typeparams,)

            @classmethod
            def _get_type_parameters(cls):
                return cls.__type_parameters__

        return types.GenericAlias(TypeParamsWrapper, typeparams)


T = TypeVar('T')


class CommaSeparatedList(Generic[T]):
    """
    A custom type for comma-separated lists compatible with Pydantic.
    """
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: str | List[str]):
        if isinstance(v, str):
            v = v.split(",")
        else:
            v = list(itertools.chain.from_iterable((x.split(",") for x in v)))
        return conlist(str, min_items=1)(list(map(str.strip, v)))
