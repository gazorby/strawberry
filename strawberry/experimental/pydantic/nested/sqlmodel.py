from typing import Any, List

from sqlalchemy.orm.relationships import RelationshipProperty

from .base import (
    NestedPydanticField,
    extract_type_list,
)


class NestedSQLModelField(NestedPydanticField):
    def _post_init(self) -> None:
        # Find the related model
        attr = getattr(self.model, self.name)
        if attr.property.__class__ is RelationshipProperty:
            self._outer_types, self.child_model = extract_type_list(
                self.model.__annotations__[self.name]
            )
            if self._outer_types:
                self._required = self._outer_types[0] is not None.__class__
            else:
                self._required = True

    @property
    def outer_types(self) -> List[Any]:
        return self._outer_types

    @property
    def required(self) -> bool:
        return self._required
