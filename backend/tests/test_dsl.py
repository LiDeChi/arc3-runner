from arc3math.dsl import Entity, State, apply_program, enumerate_programs, extensional_key, mdl, program_to_math


def s(x=2, y=2):
    return State([[0 for _ in range(5)] for _ in range(5)], (Entity("agent", "agent", x, y, 4),), 0, 0, {})


def pos(state):
    a = state.agent()
    return a.x, a.y


def test_primitives_and_combiners():
    assert pos(apply_program({"op": "identity"}, s())) == (2, 2)
    assert pos(apply_program({"op": "translate", "dx": 1, "dy": -1}, s())) == (3, 1)
    assert pos(apply_program({"op": "rotate", "k": 1}, s(1, 2))) == (2, 1)
    assert pos(apply_program({"op": "reflect", "axis": "h"}, s(1, 3))) == (1, 1)
    assert pos(apply_program({"op": "compose", "fs": [{"op": "translate", "dx": 1, "dy": 0}, {"op": "translate", "dx": 0, "dy": -1}]}, s())) == (3, 1)
    assert pos(
        apply_program(
            {
                "op": "conditional",
                "pred": {"pred": "in_region", "x0": 0, "y0": 0, "x1": 2, "y1": 4},
                "then": {"op": "translate", "dx": 1, "dy": 0},
                "else": {"op": "translate", "dx": -1, "dy": 0},
            },
            s(1, 1),
        )
    ) == (2, 1)


def test_conjugacy_law():
    gs = [{"op": "rotate", "k": k} for k in (1, 2, 3)] + [{"op": "reflect", "axis": a} for a in ("h", "v", "d", "a")]
    vectors = [(0, -1), (0, 1), (-1, 0), (1, 0), (1, -1), (-1, -1), (1, 1), (-1, 1)]
    from arc3math.dsl import transform_vector

    for g in gs:
        for dx, dy in vectors:
            conj = {"op": "conjugate", "g": g, "f": {"op": "translate", "dx": dx, "dy": dy}}
            ex, ey = transform_vector(g, dx, dy)
            direct = {"op": "translate", "dx": ex, "dy": ey}
            assert extensional_key(conj) == extensional_key(direct)


def test_enumerator_contract():
    programs = enumerate_programs(8.0)
    assert 200 <= len(programs) <= 5000
    costs = [mdl(p) for p in programs]
    assert costs == sorted(costs)
    assert len({extensional_key(p) for p in programs}) == len(programs)
    assert program_to_math({"op": "translate", "dx": 0, "dy": -1}) == "T(0,-1)"
