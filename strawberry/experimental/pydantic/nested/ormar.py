from typing import TYPE_CHECKING, List, Optional, Type

import ormar
from ormar.queryset.field_accessor import FieldAccessor
from pydantic.fields import UndefinedType
from .base import LazyModelType, NestedField, ForwardRef # type: ignore


class NestedOrmarField(NestedField):
    def _post_init(self) -> None:
        if TYPE_CHECKING:
            self.child_model: Type[ormar.Model]

        if self.name in self.model.__fields__:
            self.field = self.model.__fields__[self.name]

            if not isinstance(self.field.field_info, (ormar.ForeignKeyField, ormar.ManyToManyField)):
                return

            self.f_info = self.field.field_info
            self.child_model = self.f_info.to
            self._required = self.field.required
        else:
            self.field = getattr(self.model, self.name)
            if not isinstance(self.field, FieldAccessor):
                return
            self.f_info = self.field
            self.child_model = self.field._model
            self._required = False

    def get_strawberry_type(self) -> type:
        if isinstance(self.child_model, ForwardRef):
            # Update forward refs first so they are linked to actual mdodels
            self.model.update_forward_refs()
            self.child_model = self.f_info.to

        if getattr(self.child_model, "_strawberry_type", None):
            strawberry_type = self.child_model._strawberry_type # type: ignore
        else:
            strawberry_type = LazyModelType[self.child_model] # type: ignore

        # TODO Is it ok to make inner type optional by default for both ManyToManyField and FieldAccessor?
        if isinstance(self.f_info, (FieldAccessor, ormar.ManyToManyField)):
            strawberry_type = List[Optional[strawberry_type]]

        elif isinstance(self.f_info, ormar.ForeignKeyField):
            strawberry_type = strawberry_type

        else:
            raise Exception("Relation not supported yet")

        if isinstance(self._required, UndefinedType) or not self._required:
            strawberry_type = Optional[strawberry_type]

        return strawberry_type
