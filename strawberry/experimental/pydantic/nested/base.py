from abc import ABC, abstractmethod
from dataclasses import dataclass
from inspect import isclass
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

from typing_extensions import get_args, get_origin

from strawberry.type import StrawberryType


try:
    from typing import ForwardRef  # type: ignore
except ImportError:  # pragma: no cover
    # ForwardRef is private in python 3.6 and 3.7
    from typing import _ForwardRef as ForwardRef  # type: ignore

import pydantic
from backports.cached_property import cached_property
from pydantic.fields import UndefinedType

from strawberry.experimental.pydantic.exceptions import UnsupportedTypeError
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
        class LazyModelType(cls):
            pass

        # strawberry.LazyType wants some positional arguments
        return LazyModelType("", "", None, model)

    def resolve_type(self) -> Type:
        return self.model._strawberry_type  # type: ignore


@dataclass(frozen=True)
class LazyForwardRefType(LazyType, Generic[BaseModel, FieldName, Index]):
    """Resolve strawberry type from a pydantic model.

    This is used when a model's child is typed using a forward ref.
    This wrap the forward ref and allow to resolve the actual type
    during schema building (where all type are known) by calling `get_type_hints`.
    """

    model: pydantic.BaseModel
    name: str
    index: int

    def __class_getitem__(cls, params):
        # We need to redefine the class each time to make sure
        # that params passed to typing.Union are of distincts types
        @dataclass(frozen=True)
        class LazyForwardRefType(cls):
            pass

        model, name, index = params
        # strawberry.LazyType wants some positional arguments
        return LazyForwardRefType("", "", None, model, name, index)

    @cached_property
    def _resolve_type(self) -> Any:
        # Update type hints to resolve ForwardRefs
        typ = get_type_hints(self.model)[self.name]
        _, inner_type = extract_type_list(typ)
        return inner_type[self.index]._strawberry_type

    @property
    def _type_definition(self) -> StrawberryType:
        """Compatibility with strawberry typing system."""
        return self._resolve_type._type_definition


class NestedBackend(ABC):
    def __init__(self, name: str, model: Type[pydantic.BaseModel]) -> None:
        self.name = name
        self.model = model
        self.child_type: Optional[Union[Tuple[Any, ...], Any]] = None
        self._post_init()
        if not self.child_type:
            raise RelationFieldError()

    @abstractmethod
    def _post_init(self) -> None:
        """Called during __init__. Must fill self.child_type if field is a relation."""

    @abstractmethod
    def get_strawberry_type(self) -> object:
        """Return the corresponding strawberry type for the field."""


class RelationFieldError(Exception):
    """Field is not a relation (does not reference another type)."""


class NestedPydanticBackend(NestedBackend):
    def _post_init(self):
        self.field = self.model.__fields__[self.name]
        if isinstance(self.field.type_, ForwardRef) or (
            isclass(self.field.type_)
            and issubclass(self.field.type_, pydantic.BaseModel)
        ):
            self.child_type: Tuple[Any, ...] = (self.field.type_,)
        elif get_origin(self.field.type_) is Union and any(
            _may_be_model(t) for t in get_args(self.field.type_)
        ):
            self.child_type = get_args(self.field.type_)

    def _process_type(self, typ, idx: int = 0) -> object:
        if isinstance(typ, ForwardRef):
            return LazyForwardRefType[self.model, self.name, idx]  # type: ignore
        elif isclass(typ) and issubclass(typ, pydantic.BaseModel):
            return getattr(typ, "_strawberry_type", LazyModelType[typ])  # type: ignore
        # Already a strawberry type
        return typ

    def _process_union(self, union_types: Tuple[Any, ...]) -> Union[Any, Any]:
        """Build an Union type out of a type params.

        Python < 3.11 don't allow the `typing.Union[*params]` syntax
        so we build the union iteratively by pairs, using the following property :
        Union[a, b, c] = Union[Union[a, b], c]
        """
        assert len(union_types) > 1

        union: Union[Any, Any] = None
        for i, (typ_a, typ_b) in enumerate(zip(union_types, union_types[1:])):
            typ_a = self._process_type(typ_a, i)
            typ_b = self._process_type(typ_b, i + 1)
            union = (
                Union[typ_a, typ_b]
                if union is None
                else Union[union, Union[typ_a, typ_b]]
            )
        return union

    def get_strawberry_type(self) -> object:
        none_in_union = False
        if len(self.child_type) > 1:
            strawberry_type = self._process_union(self.child_type)
            none_in_union = any(t is None.__class__ for t in self.outer_types)
        else:
            strawberry_type = self._process_type(self.child_type[0])

        # Rebuild outer types
        for typ in self.outer_types[-1::-1]:
            strawberry_type = typ[strawberry_type]

        if none_in_union or not self.required:
            strawberry_type = Optional[strawberry_type]

        return strawberry_type

    @property
    def required(self) -> bool:
        # Check outermost type as `self.model.field.required` can be of type Undefined
        return (
            getattr(get_type_hints(self.model)[self.name], "_name", None) != "Optional"
            if isinstance(self.field.required, UndefinedType)
            else self.field.required
        )

    @cached_property
    def outer_types(self) -> List[Any]:
        return extract_type_list(self.field.outer_type_)[0]


def _may_be_model(typ: Any) -> bool:
    """Whether or not the given type may leads to a Pydantic model."""
    return (isclass(typ) and issubclass(typ, pydantic.BaseModel)) or isinstance(
        typ, ForwardRef
    )


def extract_type_list(typ: Any) -> Tuple[List[Any], Tuple[Any, ...]]:
    """Extract outer types from the given type.

    Return: ([outer_types], (inner_types))

    Exemples:
        - List[Optional[int]] -> ([List, Optional], (int,))

        If multiple inner types are returned, it means that they are
        part of a Union:
        - Optional[Union[str, int]] -> ([Optional], (str, int))
    """
    type_list: List[Any] = []
    inner: Any = typ
    while inner is not None:
        inner_type = None
        if _may_be_model(inner):
            break
        if (
            not hasattr(inner, "_name")
            or inner._name not in ["Optional", "List"]
            and not get_origin(inner) is Union
        ):
            raise UnsupportedTypeError(f"Unsupported type: {inner}")
        if inner._name == "Optional":
            optional_types = list(get_args(inner))
            optional_types.pop(optional_types.index(None.__class__))
            inner_type = optional_types[0]
            type_list.append(Optional)
        elif inner._name == "List":
            type_list.append(List)
            inner_type = get_args(inner)[0]
        elif get_origin(inner) is Union:
            inner = get_args(inner)
            break
        inner = inner_type

    return type_list, inner if isinstance(inner, tuple) else (inner,)
