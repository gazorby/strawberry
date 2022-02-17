import textwrap
from typing import List, Optional

import pytest

from sqlmodel import Field, Relationship, SQLModel

import strawberry

class City(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field()
    population: int = Field()

class Manager(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field()
    managed_team: "Team" = Relationship(back_populates="manager")


class Team(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True)
    headquarters: Optional[str] = Field(default=None)
    manager_id: int = Field(nullable=False, foreign_key="manager.id")
    manager: Manager = Relationship(back_populates="managed_team")
    heroes: List["Hero"] = Relationship(back_populates="team")


class Hero(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True)
    secret_name: str
    age: Optional[int] = Field(default=None, index=True)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id")
    team: Optional[Team] = Relationship(back_populates="heroes")


@pytest.fixture
def clear_types():
    for model in (Team, Hero, Manager, City):
        if hasattr(model, "_strawberry_type"):
            delattr(model, "_strawberry_type")


def test_all_fields(clear_types):
    @strawberry.experimental.pydantic.type(City, all_fields=True)
    class CityType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def city(self) -> CityType:
            return CityType(
                id=1, name="Gotham", population=100000
            )

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type CityType {
      name: String!
      population: Int!
      id: Int
    }

    type Query {
      city: CityType!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ city { name } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["city"]["name"] == "Gotham"


def test_basic_type_field_list(clear_types):
    @strawberry.experimental.pydantic.type(Team, fields=["name", "headquarters"])
    class TeamType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def team(self) -> TeamType:
            return TeamType(name="hobbits", headquarters="The Shire")

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type Query {
      team: TeamType!
    }

    type TeamType {
      name: String!
      headquarters: String
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ team { name } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["team"]["name"] == "hobbits"


def test_one_to_one_optional(clear_types):
    @strawberry.experimental.pydantic.type(Team, fields=["name"])
    class TeamType:
        pass

    @strawberry.experimental.pydantic.type(Hero, fields=["team"])
    class HeroType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def hero(self) -> HeroType:
            return HeroType(team=TeamType(name="Skii"))

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type HeroType {
      team: TeamType
    }

    type Query {
      hero: HeroType!
    }

    type TeamType {
      name: String!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ hero { team { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["hero"]["team"]["name"] == "Skii"


def test_one_to_one_required(clear_types):
    @strawberry.experimental.pydantic.type(Manager, fields=["name"])
    class ManagerType:
        pass

    @strawberry.experimental.pydantic.type(Team, fields=["manager"])
    class TeamType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def team(self) -> TeamType:
            return TeamType(manager=ManagerType(name="Skii"))

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type ManagerType {
      name: String!
    }

    type Query {
      team: TeamType!
    }

    type TeamType {
      manager: ManagerType!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ team { manager { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["team"]["manager"]["name"] == "Skii"


def test_nested_type_unordered(clear_types):
    @strawberry.experimental.pydantic.type(Hero, fields=["team"])
    class HeroType:
        pass

    @strawberry.experimental.pydantic.type(Team, fields=["name"])
    class TeamType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def hero(self) -> HeroType:
            return HeroType(team=TeamType(name="Skii"))

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type HeroType {
      team: TeamType
    }

    type Query {
      hero: HeroType!
    }

    type TeamType {
      name: String!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ hero { team { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["hero"]["team"]["name"] == "Skii"


def test_one_to_many(clear_types):
    @strawberry.experimental.pydantic.type(Team, fields=["heroes"])
    class TeamType:
        pass

    @strawberry.experimental.pydantic.type(Hero, fields=["name"])
    class HeroType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def team(self) -> TeamType:
            return TeamType(heroes=[HeroType(name="Skii"), HeroType(name="Chris")])

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type HeroType {
      name: String!
    }

    type Query {
      team: TeamType!
    }

    type TeamType {
      heroes: [HeroType!]!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ team { heroes { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["team"]["heroes"][0]["name"] == "Skii"
    assert result.data["team"]["heroes"][1]["name"] == "Chris"
