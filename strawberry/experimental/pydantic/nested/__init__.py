import sys
from dataclasses import Field
from typing import Any, List, Set, Type, Union

import pydantic

from strawberry.annotation import StrawberryAnnotation
from strawberry.arguments import UNSET
from strawberry.field import StrawberryField

from .base import NestedBackend, NestedPydanticBackend, RelationFieldError


try:
    # Import in second to avoid clashes
    from ormar import Model

    from .ormar import NestedOrmarBackend
except ModuleNotFoundError:  # pragma: no cover
    NestedOrmarBackend = None

try:
    # Import in second to avoid clashes
    from sqlmodel import SQLModel

    from .sqlmodel import NestedSQLModelBackend
except ModuleNotFoundError:  # pragma: no cover
    NestedSQLModelBackend = None


def _nested_field_factory(
    name: str,
    model: Union[Type["Model"], Type["SQLModel"], Type[pydantic.BaseModel]],
) -> NestedBackend:
    if NestedOrmarBackend and issubclass(model, Model):
        return NestedOrmarBackend(name, model)
    elif NestedSQLModelBackend and issubclass(model, SQLModel):
        return NestedSQLModelBackend(name, model)
    assert issubclass(model, pydantic.BaseModel)
    return NestedPydanticBackend(name, model)


def process_nested_fields(
    type_class: Any, fields_set: Set[str], model: Type[pydantic.BaseModel]
) -> List[Field]:
    """Infer strawberry types from relations in pydantic based models."""
    fields: List[Field] = []
    for name in fields_set:
        if name in getattr(type_class, "__annotations__", {}):
            continue
        try:
            field = _nested_field_factory(name, model)
        except RelationFieldError:
            # The field is not a relation, so there is no nested model
            continue

        strawberry_type = field.get_strawberry_type()
        module = sys.modules[type_class.__module__]

        strawberry_field = StrawberryField(
            python_name=name,
            graphql_name=None,
            type_annotation=StrawberryAnnotation(
                annotation=strawberry_type,
                namespace=module.__dict__,
            ),
            origin=type_class,
            default=getattr(type_class, name, UNSET),
        )

        fields.append(strawberry_field)

    return fields
