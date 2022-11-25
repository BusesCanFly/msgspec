import enum
import datetime
import uuid
from base64 import b64encode
from copy import deepcopy
from collections import namedtuple
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Literal,
    NamedTuple,
    Set,
    Tuple,
    TypedDict,
    Union,
)

import pytest

import msgspec
from msgspec._utils import merge_json

from utils import temp_module

try:
    from typing import Annotated
except ImportError:
    try:
        from typing_extensions import Annotated
    except ImportError:
        pytestmark = pytest.mark.skip("Annotated types not available")


@pytest.mark.parametrize(
    "a,b,sol",
    [
        (
            {"a": {"b": {"c": 1}}},
            {"a": {"b": {"d": 2}}},
            {"a": {"b": {"c": 1, "d": 2}}},
        ),
        ({"a": {"b": {"c": 1}}}, {"a": {"b": 2}}, {"a": {"b": 2}}),
        ({"a": [1, 2]}, {"a": [3, 4]}, {"a": [1, 2, 3, 4]}),
        ({"a": {"b": 1}}, {"a2": 3}, {"a": {"b": 1}, "a2": 3}),
        ({"a": 1}, {}, {"a": 1}),
    ],
)
def test_merge_json(a, b, sol):
    a_orig = deepcopy(a)
    b_orig = deepcopy(b)
    res = merge_json(a, b)
    assert res == sol
    assert a == a_orig
    assert b == b_orig


def type_index(typ, args):
    try:
        return typ[args]
    except TypeError:
        pytest.skip("Not supported in Python 3.8")


def test_any():
    assert msgspec.json.schema(Any) == {}


def test_raw():
    assert msgspec.json.schema(msgspec.Raw) == {}


def test_msgpack_ext():
    with pytest.raises(TypeError):
        assert msgspec.json.schema(msgspec.msgpack.Ext)


def test_custom():
    with pytest.raises(TypeError, match="Custom types"):
        assert msgspec.json.schema(uuid.UUID)

    schema = {"type": "string", "pattern": "uuid4"}

    assert (
        msgspec.json.schema(
            Annotated[uuid.UUID, msgspec.Meta(extra_json_schema=schema)]
        )
        == schema
    )


def test_none():
    assert msgspec.json.schema(None) == {"type": "null"}


def test_bool():
    assert msgspec.json.schema(bool) == {"type": "boolean"}


def test_int():
    assert msgspec.json.schema(int) == {"type": "integer"}


def test_float():
    assert msgspec.json.schema(float) == {"type": "number"}


def test_string():
    assert msgspec.json.schema(str) == {"type": "string"}


@pytest.mark.parametrize("typ", [bytes, bytearray])
def test_binary(typ):
    assert msgspec.json.schema(typ) == {
        "type": "string",
        "contentEncoding": "base64",
    }


def test_datetime():
    assert msgspec.json.schema(datetime.datetime) == {
        "type": "string",
        "format": "date-time",
    }


@pytest.mark.parametrize(
    "typ", [list, tuple, set, frozenset, List, Tuple, Set, FrozenSet]
)
def test_sequence_any(typ):
    assert msgspec.json.schema(typ) == {"type": "array"}


@pytest.mark.parametrize(
    "cls", [list, tuple, set, frozenset, List, Tuple, Set, FrozenSet]
)
def test_sequence_typed(cls):
    args = (int, ...) if cls in (tuple, Tuple) else int
    typ = type_index(cls, args)
    assert msgspec.json.schema(typ) == {"type": "array", "items": {"type": "integer"}}


@pytest.mark.parametrize("cls", [tuple, Tuple])
def test_tuple(cls):
    typ = type_index(cls, (int, float, str))
    assert msgspec.json.schema(typ) == {
        "type": "array",
        "minItems": 3,
        "maxItems": 3,
        "items": False,
        "prefixItems": [
            {"type": "integer"},
            {"type": "number"},
            {"type": "string"},
        ],
    }


@pytest.mark.parametrize("cls", [tuple, Tuple])
def test_empty_tuple(cls):
    typ = type_index(cls, ())
    assert msgspec.json.schema(typ) == {
        "type": "array",
        "minItems": 0,
        "maxItems": 0,
    }


@pytest.mark.parametrize("typ", [dict, Dict])
def test_dict_any(typ):
    assert msgspec.json.schema(typ) == {"type": "object"}


@pytest.mark.parametrize("cls", [dict, Dict])
def test_dict_typed(cls):
    typ = type_index(cls, (str, int))
    assert msgspec.json.schema(typ) == {
        "type": "object",
        "additionalProperties": {"type": "integer"},
    }


def test_int_enum():
    class Example(enum.IntEnum):
        C = 1
        B = 3
        A = 2

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {"Example": {"title": "Example", "enum": [1, 2, 3]}},
    }


def test_enum():
    class Example(enum.Enum):
        """A docstring"""

        C = "x"
        B = "z"
        A = "y"

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "description": "A docstring",
                "enum": ["A", "B", "C"],
            }
        },
    }


def test_int_literal():
    assert msgspec.json.schema(Literal[3, 1, 2]) == {"enum": [1, 2, 3]}


def test_str_literal():
    assert msgspec.json.schema(Literal["c", "a", "b"]) == {"enum": ["a", "b", "c"]}


def test_struct_object():
    class Point(msgspec.Struct):
        x: int
        y: int

    class Polygon(msgspec.Struct):
        """An example docstring"""

        vertices: List[Point]
        name: Union[str, None] = None
        metadata: Dict[str, str] = {}

    assert msgspec.json.schema(Polygon) == {
        "$ref": "#/$defs/Polygon",
        "$defs": {
            "Polygon": {
                "title": "Polygon",
                "description": "An example docstring",
                "type": "object",
                "properties": {
                    "vertices": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/Point"},
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "metadata": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "default": {},
                    },
                },
                "required": ["vertices"],
            },
            "Point": {
                "title": "Point",
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    }


def test_struct_array_like():
    class Example(msgspec.Struct, array_like=True):
        """An example docstring"""

        a: int
        b: str
        c: List[int] = []
        d: Dict[str, int] = {}

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "description": "An example docstring",
                "type": "array",
                "prefixItems": [
                    {"type": "integer"},
                    {"type": "string"},
                    {"type": "array", "items": {"type": "integer"}, "default": []},
                    {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                        "default": {},
                    },
                ],
                "minItems": 2,
            }
        },
    }


def test_struct_no_fields():
    class Example(msgspec.Struct):
        pass

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "type": "object",
                "properties": {},
                "required": [],
            }
        },
    }


def test_struct_object_tagged():
    class Point(msgspec.Struct, tag=True):
        x: int
        y: int

    assert msgspec.json.schema(Point) == {
        "$ref": "#/$defs/Point",
        "$defs": {
            "Point": {
                "title": "Point",
                "type": "object",
                "properties": {
                    "type": {"enum": ["Point"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["type", "x", "y"],
            }
        },
    }


def test_struct_array_tagged():
    class Point(msgspec.Struct, tag=True, array_like=True):
        x: int
        y: int

    assert msgspec.json.schema(Point) == {
        "$ref": "#/$defs/Point",
        "$defs": {
            "Point": {
                "title": "Point",
                "type": "array",
                "prefixItems": [
                    {"enum": ["Point"]},
                    {"type": "integer"},
                    {"type": "integer"},
                ],
                "minItems": 3,
            }
        },
    }


def test_typing_namedtuple():
    class Example(NamedTuple):
        """An example docstring"""

        a: str
        b: bool
        c: int = 0

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "description": "An example docstring",
                "type": "array",
                "prefixItems": [
                    {"type": "string"},
                    {"type": "boolean"},
                    {"type": "integer", "default": 0},
                ],
                "minItems": 2,
                "maxItems": 3,
            }
        },
    }


def test_collections_namedtuple():
    Example = namedtuple("Example", ["a", "b", "c"], defaults=(0,))

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "type": "array",
                "prefixItems": [{}, {}, {"default": 0}],
                "minItems": 2,
                "maxItems": 3,
            }
        },
    }


@pytest.mark.parametrize("use_typing_extensions", [False, True])
def test_typeddict(use_typing_extensions):
    if use_typing_extensions:
        tex = pytest.importorskip("typing_extensions")
        cls = tex.TypedDict
    else:
        cls = TypedDict

    class Example(cls):
        """An example docstring"""

        a: str
        b: bool
        c: int

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "description": "An example docstring",
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "boolean"},
                    "c": {"type": "integer"},
                },
                "required": ["a", "b", "c"],
            }
        },
    }


@pytest.mark.parametrize("use_typing_extensions", [False, True])
def test_typeddict_optional(use_typing_extensions):
    if use_typing_extensions:
        tex = pytest.importorskip("typing_extensions")
        cls = tex.TypedDict
    else:
        cls = TypedDict

    class Base(cls):
        a: str
        b: bool

    class Example(Base, total=False):
        """An example docstring"""

        c: int

    if not hasattr(Example, "__required_keys__"):
        # This should be Python 3.8, builtin typing only
        pytest.skip("partially optional TypedDict not supported")

    assert msgspec.json.schema(Example) == {
        "$ref": "#/$defs/Example",
        "$defs": {
            "Example": {
                "title": "Example",
                "description": "An example docstring",
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "boolean"},
                    "c": {"type": "integer"},
                },
                "required": ["a", "b"],
            }
        },
    }


@pytest.mark.parametrize("use_union_operator", [False, True])
def test_union(use_union_operator):
    class Example(msgspec.Struct):
        x: int
        y: int

    if use_union_operator:
        try:
            typ = int | str | Example
        except TypeError:
            pytest.skip("Union operator not supported")
    else:
        typ = Union[int, str, Example]

    assert msgspec.json.schema(typ) == {
        "anyOf": [
            {"type": "integer"},
            {"type": "string"},
            {"$ref": "#/$defs/Example"},
        ],
        "$defs": {
            "Example": {
                "title": "Example",
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"],
            }
        },
    }


def test_struct_tagged_union():
    class Point(msgspec.Struct, tag=True):
        x: int
        y: int

    class Point3D(Point):
        z: int

    assert msgspec.json.schema(Union[Point, Point3D]) == {
        "anyOf": [{"$ref": "#/$defs/Point"}, {"$ref": "#/$defs/Point3D"}],
        "discriminator": {
            "mapping": {"Point": "#/$defs/Point", "Point3D": "#/$defs/Point3D"},
            "propertyName": "type",
        },
        "$defs": {
            "Point": {
                "properties": {
                    "type": {"enum": ["Point"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["type", "x", "y"],
                "title": "Point",
                "type": "object",
            },
            "Point3D": {
                "properties": {
                    "type": {"enum": ["Point3D"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "z": {"type": "integer"},
                },
                "required": ["type", "x", "y", "z"],
                "title": "Point3D",
                "type": "object",
            },
        },
    }


def test_struct_tagged_union_mixed_types():
    class Point(msgspec.Struct, tag=True):
        x: int
        y: int

    class Point3D(Point):
        z: int

    assert msgspec.json.schema(Union[Point, Point3D, int, float]) == {
        "anyOf": [
            {"type": "integer"},
            {"type": "number"},
            {
                "anyOf": [{"$ref": "#/$defs/Point"}, {"$ref": "#/$defs/Point3D"}],
                "discriminator": {
                    "mapping": {"Point": "#/$defs/Point", "Point3D": "#/$defs/Point3D"},
                    "propertyName": "type",
                },
            },
        ],
        "$defs": {
            "Point": {
                "properties": {
                    "type": {"enum": ["Point"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["type", "x", "y"],
                "title": "Point",
                "type": "object",
            },
            "Point3D": {
                "properties": {
                    "type": {"enum": ["Point3D"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "z": {"type": "integer"},
                },
                "required": ["type", "x", "y", "z"],
                "title": "Point3D",
                "type": "object",
            },
        },
    }


def test_struct_array_union():
    class Point(msgspec.Struct, array_like=True, tag=True):
        x: int
        y: int

    class Point3D(Point):
        z: int

    assert msgspec.json.schema(Union[Point, Point3D]) == {
        "anyOf": [{"$ref": "#/$defs/Point"}, {"$ref": "#/$defs/Point3D"}],
        "$defs": {
            "Point": {
                "minItems": 3,
                "prefixItems": [
                    {"enum": ["Point"]},
                    {"type": "integer"},
                    {"type": "integer"},
                ],
                "title": "Point",
                "type": "array",
            },
            "Point3D": {
                "minItems": 4,
                "prefixItems": [
                    {"enum": ["Point3D"]},
                    {"type": "integer"},
                    {"type": "integer"},
                    {"type": "integer"},
                ],
                "title": "Point3D",
                "type": "array",
            },
        },
    }


@pytest.mark.parametrize(
    "field, constraint",
    [
        ("ge", "minimum"),
        ("gt", "exclusiveMinimum"),
        ("le", "maximum"),
        ("lt", "exclusiveMaximum"),
        ("multiple_of", "multipleOf"),
    ],
)
def test_numeric_metadata(field, constraint):
    typ = Annotated[int, msgspec.Meta(**{field: 2})]
    assert msgspec.json.schema(typ) == {"type": "integer", constraint: 2}


@pytest.mark.parametrize(
    "field, val, constraint",
    [
        ("pattern", "[a-z]*", "pattern"),
        ("min_length", 0, "minLength"),
        ("max_length", 3, "maxLength"),
    ],
)
def test_string_metadata(field, val, constraint):
    typ = Annotated[str, msgspec.Meta(**{field: val})]
    assert msgspec.json.schema(typ) == {"type": "string", constraint: val}


@pytest.mark.parametrize("typ", [bytes, bytearray])
@pytest.mark.parametrize(
    "field, n, constraint",
    [("min_length", 2, "minLength"), ("max_length", 7, "maxLength")],
)
def test_binary_metadata(typ, field, n, constraint):
    n2 = len(b64encode(b"x" * n))
    typ = Annotated[typ, msgspec.Meta(**{field: n})]
    assert msgspec.json.schema(typ) == {
        "type": "string",
        constraint: n2,
        "contentEncoding": "base64",
    }


@pytest.mark.parametrize("typ", [list, tuple, set, frozenset])
@pytest.mark.parametrize(
    "field, constraint",
    [("min_length", "minItems"), ("max_length", "maxItems")],
)
def test_array_metadata(typ, field, constraint):
    typ = Annotated[typ, msgspec.Meta(**{field: 2})]
    assert msgspec.json.schema(typ) == {"type": "array", constraint: 2}


@pytest.mark.parametrize(
    "field, constraint",
    [("min_length", "minProperties"), ("max_length", "maxProperties")],
)
def test_object_metadata(field, constraint):
    typ = Annotated[dict, msgspec.Meta(**{field: 2})]
    assert msgspec.json.schema(typ) == {"type": "object", constraint: 2}


def test_generic_metadata():
    typ = Annotated[
        int,
        msgspec.Meta(
            title="the title",
            description="the description",
            examples=[1, 2, 3],
            extra_json_schema={"title": "an override", "default": 1},
        ),
    ]
    assert msgspec.json.schema(typ) == {
        "type": "integer",
        "title": "an override",
        "description": "the description",
        "examples": [1, 2, 3],
        "default": 1,
    }


def test_component_names_collide():
    s1 = """
    import msgspec
    Ex = msgspec.defstruct("Ex", [("x", int), ("y", int)])
    """

    s2 = """
    import msgspec
    Ex = msgspec.defstruct("Ex", [("a", str), ("b", str)])
    """

    with temp_module(s1) as m1, temp_module(s2) as m2:
        (r1, r2), components = msgspec.json.schema_components([m1.Ex, m2.Ex])

    assert r1 == {"$ref": f"#/$defs/{m1.__name__}.Ex"}
    assert r2 == {"$ref": f"#/$defs/{m2.__name__}.Ex"}
    assert components == {
        f"{m1.__name__}.Ex": {
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x", "y"],
            "title": "Ex",
            "type": "object",
        },
        f"{m2.__name__}.Ex": {
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a", "b"],
            "title": "Ex",
            "type": "object",
        },
    }


def test_schema_components_collects_subtypes():
    class ExEnum(enum.Enum):
        A = 1

    class ExStruct(msgspec.Struct):
        b: Union[Set[FrozenSet[ExEnum]], int]

    class ExDict(TypedDict):
        c: Tuple[ExStruct, ...]

    class ExTuple(NamedTuple):
        d: List[ExDict]

    (s,), components = msgspec.json.schema_components([Dict[str, ExTuple]])

    r1 = {"$ref": "#/$defs/ExEnum"}
    r2 = {"$ref": "#/$defs/ExStruct"}
    r3 = {"$ref": "#/$defs/ExDict"}
    r4 = {"$ref": "#/$defs/ExTuple"}

    assert s == {"type": "object", "additionalProperties": r4}
    assert components == {
        "ExEnum": {"enum": ["A"], "title": "ExEnum"},
        "ExStruct": {
            "type": "object",
            "title": "ExStruct",
            "properties": {
                "b": {
                    "anyOf": [
                        {"items": {"items": r1, "type": "array"}, "type": "array"},
                        {"type": "integer"},
                    ]
                }
            },
            "required": ["b"],
        },
        "ExDict": {
            "title": "ExDict",
            "type": "object",
            "properties": {"c": {"items": r2, "type": "array"}},
            "required": ["c"],
        },
        "ExTuple": {
            "title": "ExTuple",
            "type": "array",
            "prefixItems": [{"items": r3, "type": "array"}],
            "maxItems": 1,
            "minItems": 1,
        },
    }


def test_ref_template():
    class Ex1(msgspec.Struct):
        a: int

    class Ex2(msgspec.Struct):
        b: Ex1

    (s1, s2), components = msgspec.json.schema_components(
        [Ex1, Ex2], ref_template="#/definitions/{name}"
    )

    assert s1 == {"$ref": "#/definitions/Ex1"}
    assert s2 == {"$ref": "#/definitions/Ex2"}

    assert components == {
        "Ex1": {
            "title": "Ex1",
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
        "Ex2": {
            "title": "Ex2",
            "type": "object",
            "properties": {"b": s1},
            "required": ["b"],
        },
    }