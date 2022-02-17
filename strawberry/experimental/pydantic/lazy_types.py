from dataclasses import dataclass
from typing import Generic, Type, TypeVar, get_type_hints

import pydantic
from typing_extensions import get_args

from strawberry.lazy_type import LazyType


BaseModel = TypeVar("BaseModel")
FieldName = TypeVar("FieldName")
Index = TypeVar("Index")


@dataclass(frozen=True)
class LazyModelType(LazyType, Generic[BaseModel]):
    """Resolve strawberry type from a pydantic model.

    This is used when a model's child that hasn't been discovered yet.
    It will be resolved during schema building, where all
    strawberry types generated from a pydantic model have been
    attached to it.
    """

    model: pydantic.BaseModel

    def __class_getitem__(cls, model):
        # We need to redefine the class each time to make sure
        # that params passed to typing.Union are of distincts types
        @dataclass(frozen=True)
        class LazyModelType(cls):  # type: ignore
            pass

        # strawberry.LazyType wants some positional arguments
        return LazyModelType("", "", None, model)

    def resolve_type(self) -> Type:
        return self.model._strawberry_type  # type: ignore


@dataclass(frozen=True)
class LazyForwardRefType(LazyType, Generic[BaseModel, FieldName]):
    """Resolve strawberry type from a pydantic model.

    This is used when a model's child is typed using a forward ref.
    This wrap the forward ref and allow to resolve the actual type
    during schema building (where all type are known) by calling `get_type_hints`.
    """

    model: pydantic.BaseModel
    name: str
    # index: int

    def __class_getitem__(cls, params):
        # We need to redefine the class each time to make sure
        # that params passed to typing.Union are of distincts types
        @dataclass(frozen=True)
        class LazyForwardRefType(cls):  # type: ignore
            pass

        model, name = params
        # strawberry.LazyType wants some positional arguments
        return LazyForwardRefType("", "", None, model, name)

    def resolve_type(self) -> Type:
        # Update type hints to resolve ForwardRefs
        typ = get_type_hints(self.model)[self.name]
        try:
            inner_type = get_args(typ)[0]
        except IndexError:
            inner_type = typ
        return inner_type._strawberry_type
