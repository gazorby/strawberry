from typing import List, Optional, Union

import pydantic


# ForwardRef
class UserLazy(pydantic.BaseModel):
    hobby: "HobbyLazy"


class HobbyLazy(pydantic.BaseModel):
    name: str


class BranchA(pydantic.BaseModel):
    field_a: str


class BranchB(pydantic.BaseModel):
    field_b: int


# Union and ForwardRef
class UserUnionLazy(pydantic.BaseModel):
    union_field: Union["BranchA", "BranchB"]


# List and ForwardRef
class UserListLazy(pydantic.BaseModel):
    list_field: List["BranchB"]


# Optional and ForwardRef
class UserOptionalLazy(pydantic.BaseModel):
    optional_field: Optional["BranchB"]
