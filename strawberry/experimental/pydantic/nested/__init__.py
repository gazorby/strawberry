from dataclasses import Field
import sys
from typing import Any, List, Set, Type
import pydantic

from strawberry.field import StrawberryField

from strawberry.annotation import StrawberryAnnotation

from strawberry.arguments import UNSET

from .base import (
    RelationFieldError,
    NestedPydanticField,
    NestedField,
)

try:
    from .ormar import NestedOrmarField

    # Import in second to avoid clashes
    import ormar
except ModuleNotFoundError:
    NestedOrmarField = None

try:
    from .sqlmodel import NestedSQLModelField

    # Import in second to avoid clashes
    import sqlmodel
except ModuleNotFoundError:
    NestedSQLModelField = None


def _nested_field_factory(name, model) -> NestedField:
    if NestedOrmarField and issubclass(model, ormar.Model):
        return NestedOrmarField(name, model)
    elif NestedSQLModelField and issubclass(model, sqlmodel.SQLModel):
        return NestedSQLModelField(name, model)
    elif issubclass(model, pydantic.BaseModel):
        return NestedPydanticField(name, model)

    raise Exception("Nested {model} is not supported.")


def process_nested_fields(
    type_class: Any, fields_set: Set[str], model: Type[pydantic.BaseModel]
) -> List[Field]:
    """Infer strawberry types from relations in ormar models."""
    fields: List[Field] = []
    for name in fields_set:
        if name in type_class.__annotations__:
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
