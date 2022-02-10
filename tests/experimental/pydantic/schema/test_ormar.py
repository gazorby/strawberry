import ormar
from typing import List, Optional, ForwardRef
import strawberry
import textwrap
import databases
import sqlalchemy
import pytest


database = databases.Database("sqlite:///db.sqlite")
metadata = sqlalchemy.MetaData()

MasterRef = ForwardRef("Hero")


class Manager(ormar.Model):
    class Meta:
        database = database
        metadata = metadata

    id: Optional[int] = ormar.Integer(primary_key=True, default=None)
    name: str = ormar.String(max_length=255)


class Team(ormar.Model):
    class Meta:
        database = database
        metadata = metadata

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(index=True, max_length=255)
    headquarters: Optional[str] = ormar.String(nullable=True, max_length=255)
    manager: Manager = ormar.ForeignKey(
        Manager, nullable=False, related_name="managed_teams"
    )
    referrers: List[Manager] = ormar.ManyToMany(Manager, related_name="referring_teams")


class Hero(ormar.Model):
    class Meta:
        database = database
        metadata = metadata

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(index=True, max_length=255)
    secret_name: str
    age: Optional[int] = ormar.Integer(default=None, index=True, nullable=True)
    master: Optional[MasterRef] = ormar.ForeignKey(
        MasterRef, nullable=True, default=None
    )
    team: Optional[int] = ormar.ForeignKey(Team, nullable=True, related_name="heroes")


@pytest.fixture
def clear_types():
    for model in (Team, Hero, Manager):
        if hasattr(model, "_strawberry_type"):
            delattr(model, "_strawberry_type")


def test_all_fields(clear_types):
    @strawberry.experimental.pydantic.type(Manager, all_fields=True)
    class ManagerType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def manager(self) -> ManagerType:
            return ManagerType(id=1, name="Dave")

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type ManagerType {
      name: String!
      id: Int
    }

    type Query {
      manager: ManagerType!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ manager { name } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["manager"]["name"] == "Dave"


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


def test_reverse_relation(clear_types):
    @strawberry.experimental.pydantic.type(Team, related=["heroes"])
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
      heroes: [HeroType]
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ team { heroes { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["team"]["heroes"][0]["name"] == "Skii"
    assert result.data["team"]["heroes"][1]["name"] == "Chris"


def test_one_to_many(clear_types):
    @strawberry.experimental.pydantic.type(Team, related=["referrers"])
    class TeamType:
        pass

    @strawberry.experimental.pydantic.type(Manager, fields=["name"])
    class ManagerType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def team(self) -> TeamType:
            return TeamType(
                referrers=[ManagerType(name="Skii"), ManagerType(name="Chris")]
            )

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type ManagerType {
      name: String!
    }

    type Query {
      team: TeamType!
    }

    type TeamType {
      referrers: [ManagerType]
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ team { referrers { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["team"]["referrers"][0]["name"] == "Skii"
    assert result.data["team"]["referrers"][1]["name"] == "Chris"


def test_forwardref(clear_types):
    @strawberry.experimental.pydantic.type(Hero, fields=["master", "name"])
    class HeroType:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def hero(self) -> HeroType:
            return HeroType(name="Chris", master=HeroType(name="Skii", master=None))

    schema = strawberry.Schema(query=Query)

    expected_schema = """
    type HeroType {
      name: String!
      master: HeroType
    }

    type Query {
      hero: HeroType!
    }
    """

    assert str(schema) == textwrap.dedent(expected_schema).strip()

    query = "{ hero { master { name } } }"

    result = schema.execute_sync(query)

    assert not result.errors
    assert result.data["hero"]["master"]["name"] == "Skii"
