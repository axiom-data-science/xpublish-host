import itertools
import types
import weakref
from typing import (
    Generic,
    List,
    TypeVar,
)


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
    def validate(cls, v: str | List[str], values=None, field=None):
        if isinstance(v, str):
            v = v.split(",")
        else:
            v = list(itertools.chain.from_iterable((x.split(",") for x in v)))
        v = list(map(str.strip, v))
        if len(v) < 1:
            raise ValueError("List must contain at least one item")
        return v
