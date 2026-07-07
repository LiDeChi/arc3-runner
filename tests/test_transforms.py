import pytest

from server.transforms import (
    ColorMap,
    Compose,
    Conditional,
    Identity,
    Mirror,
    Periodic,
    Rotate,
    Scale,
    Toggle,
    Translate,
    from_spec,
)


def test_identity_round_trips_grid_and_spec() -> None:
    transform = Identity()
    grid = [[0, 1], [2, 0]]

    assert transform.apply(grid) == grid
    assert transform.complexity == 0
    assert transform.readable() == "I"
    assert from_spec(transform.to_spec()).equals(transform)


def test_translate_moves_non_background_cells_with_clipping() -> None:
    grid = [[0, 1, 0], [0, 2, 0], [0, 0, 3]]
    transform = Translate(dx=1, dy=-1)

    assert transform.apply(grid, background_color=0) == [
        [0, 0, 2],
        [0, 0, 0],
        [0, 0, 0],
    ]
    assert transform.complexity == 1
    assert transform.readable() == "T(1,-1)"


def test_rotate_mirror_scale_and_color_map_apply_to_grid() -> None:
    grid = [[1, 2], [3, 4]]

    assert Rotate(1).apply(grid) == [[3, 1], [4, 2]]
    assert Rotate(1).complexity == 2
    assert Mirror("x").apply(grid) == [[3, 4], [1, 2]]
    assert Mirror("y").apply(grid) == [[2, 1], [4, 3]]
    assert Mirror("diag").apply(grid) == [[1, 3], [2, 4]]
    assert Scale(2).apply([[1, 2]]) == [[1, 1, 2, 2], [1, 1, 2, 2]]
    assert ColorMap({1: 9, 4: 7}).apply(grid) == [[9, 2], [3, 7]]
    assert ColorMap({3: 5}).readable() == "C{3->5}"


def test_toggle_flips_cells_between_background_and_toggle_color() -> None:
    transform = Toggle(cells=[(0, 0), (2, 1)], color=8)

    assert transform.apply([[0, 0, 0], [0, 5, 0]], background_color=0) == [
        [8, 0, 0],
        [0, 5, 8],
    ]
    assert transform.apply([[8, 0], [0, 0]], background_color=0) == [[0, 0], [0, 0]]
    assert transform.complexity == 3


def test_compose_uses_math_order_and_serializes_nested_specs() -> None:
    transform = Compose(Rotate(1), Translate(0, -1))
    grid = [[0, 1], [0, 2]]

    assert transform.readable() == "R90 ∘ T(0,-1)"
    assert transform.complexity == 4
    assert transform.apply(grid, background_color=0) == [[0, 0], [0, 2]]
    assert from_spec(transform.to_spec()).equals(transform)


def test_conditional_chooses_branch_by_coordinate_predicate() -> None:
    transform = Conditional(
        pred={"axis": "x", "op": ">=", "value": 2},
        if_true=ColorMap({1: 9}),
        if_false=Identity(),
    )

    assert transform.apply([[1, 1, 1], [0, 1, 1]]) == [[1, 1, 9], [0, 1, 9]]
    assert transform.complexity == 5
    assert transform.to_spec()["op"] == "conditional"


def test_periodic_switches_transform_after_n_steps() -> None:
    transform = Periodic(n=2, f=Translate(1, 0), g=Translate(0, 1))
    grid = [[0, 7], [0, 0]]

    assert transform.apply(grid, background_color=0, step_index=0) == [[0, 0], [0, 0]]
    assert transform.apply(grid, background_color=0, step_index=2) == [[0, 0], [0, 7]]
    assert transform.readable() == "[T(1,0)]*2 then T(0,1)"
    assert from_spec(transform.to_spec()).equals(transform)


def test_from_spec_accepts_plan_shape_and_rejects_unknown_ops() -> None:
    transform = from_spec(
        {
            "op": "compose",
            "fs": [
                {"op": "rotate", "k": 1},
                {"op": "translate", "dx": 0, "dy": -1},
            ],
        }
    )

    assert isinstance(transform, Compose)
    assert transform.readable() == "R90 ∘ T(0,-1)"
    with pytest.raises(ValueError, match="Unknown transform op"):
        from_spec({"op": "teleport"})


def test_invalid_grids_and_parameters_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="rectangular"):
        Translate(1, 0).apply([[0], [0, 1]])
    with pytest.raises(ValueError, match="axis"):
        Mirror("z")
    with pytest.raises(ValueError, match="factor"):
        Scale(0)
