from typing import List, Optional, Type

import ormar
from ormar import Model
from ormar.queryset.field_accessor import FieldAccessor
from pydantic.fields import UndefinedType

from .base import ForwardRef, LazyModelType, NestedBackend  # type: ignore


class NestedOrmarBackend(NestedBackend):
    def _post_init(self) -> None:
        if self.name in self.model.__fields__:
            self.field = self.model.__fields__[self.name]

            if not isinstance(
                self.field.field_info, (ormar.ForeignKeyField, ormar.ManyToManyField)
            ):
                return

            self.f_info = self.field.field_info
            self.f_accessor = None
            self.child_type: Optional[Type["Model"]] = self.f_info.to
            self._required = self.field.required
        elif isinstance(getattr(self.model, self.name, None), FieldAccessor):
            self.field = getattr(self.model, self.name)
            assert isinstance(self.field, FieldAccessor)
            self.f_accessor = self.field
            self.child_type = self.field._model
            self._required = False

    def get_strawberry_type(self) -> type:
        if isinstance(self.child_type, ForwardRef):
            # Update forward refs first so they are linked to actual mdodels
            self.model.update_forward_refs()
            self.child_type = self.f_info.to

        if getattr(self.child_type, "_strawberry_type", None):
            strawberry_type = self.child_type._strawberry_type  # type: ignore
        else:
            strawberry_type = LazyModelType[self.child_type]  # type: ignore

        # TODO Is it ok to make inner type optional by default
        # for both ManyToManyField and FieldAccessor?
        if self.f_accessor is not None or isinstance(
            self.f_info, ormar.ManyToManyField
        ):
            strawberry_type = List[Optional[strawberry_type]]  # type: ignore
        else:
            strawberry_type = strawberry_type

        if isinstance(self._required, UndefinedType) or not self._required:
            strawberry_type = Optional[strawberry_type]

        return strawberry_type
