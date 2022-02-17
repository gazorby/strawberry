try:
    from typing import ForwardRef  # type: ignore
except ImportError:  # pragma: no cover
    # ForwardRef is private in python 3.6 and 3.7
    from typing import _ForwardRef as ForwardRef  # type: ignore

from importlib.util import find_spec
from inspect import isclass
from typing import TYPE_CHECKING, Any, List, Optional, Type

from pydantic.fields import UndefinedType
from pydantic import BaseModel

from .lazy_types import LazyModelType


_ormar_found = find_spec("ormar")
_sqlmodel_found = find_spec("sqlmodel")

if TYPE_CHECKING:
    from ormar import Model


def replace_ormar_types(type_: Any, model: Type[BaseModel], name: str):
    from ormar import ForeignKeyField, ManyToManyField
    from ormar.queryset.field_accessor import FieldAccessor

    if name in model.__fields__:
        field = model.__fields__[name]

        if not isinstance(field.field_info, (ForeignKeyField, ManyToManyField)):
            return type_

        f_info = field.field_info
        f_accessor = None
        child_type: Optional[Type["Model"]] = f_info.to
        _required = field.required
    elif isinstance(getattr(model, name, None), FieldAccessor):
        field = getattr(model, name)
        assert isinstance(field, FieldAccessor)
        f_accessor = field
        child_type = field._model
        _required = False
    if isinstance(child_type, ForwardRef):
        # Update forward refs first so they are linked to actual mdodels
        model.update_forward_refs()
        child_type = f_info.to

    if getattr(child_type, "_strawberry_type", None):
        strawberry_type = child_type._strawberry_type  # type: ignore
    else:
        strawberry_type = LazyModelType[child_type]  # type: ignore

    # TODO Is it ok to make inner type optional by default
    # for both ManyToManyField and FieldAccessor?
    if f_accessor is not None or isinstance(f_info, ManyToManyField):
        strawberry_type = List[Optional[strawberry_type]]  # type: ignore
    else:
        strawberry_type = strawberry_type

    if isinstance(_required, UndefinedType) or not _required:
        strawberry_type = Optional[strawberry_type]

    return strawberry_type


def is_sqlmodel_field(field) -> bool:
    if not _sqlmodel_found:
        return False
    from sqlalchemy.orm.relationships import RelationshipProperty

    return getattr(field, "property", None).__class__ is RelationshipProperty


def is_ormar_field(field) -> bool:
    if not _ormar_found:
        return False
    from ormar.queryset.field_accessor import FieldAccessor

    return isinstance(field, FieldAccessor)


def is_ormar_model(model: Type[BaseModel]) -> bool:
    from ormar import Model

    return isclass(model) and issubclass(model, Model)


def is_orm_field(field) -> bool:
    return is_ormar_field(field) or is_sqlmodel_field(field)
