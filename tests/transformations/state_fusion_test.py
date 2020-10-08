# Copyright 2019-2020 ETH Zurich and the DaCe authors. All rights reserved.
import dace
from dace.transformation.interstate import StateFusion


# Inter-state condition tests
def test_fuse_assignments():
    """
    Two states in which the interstate assignment depends on an interstate
    value going into the first state. Should fail.
    """
    sdfg = dace.SDFG('state_fusion_test')
    state1 = sdfg.add_state()
    state2 = sdfg.add_state()
    state3 = sdfg.add_state()
    sdfg.add_edge(state1, state2, dace.InterstateEdge(assignments=dict(k=1)))
    sdfg.add_edge(state2, state3,
                  dace.InterstateEdge(assignments=dict(k='k + 1')))
    sdfg.apply_transformations_repeated(StateFusion, strict=True)
    assert sdfg.number_of_nodes() == 3


def test_fuse_assignment_in_use():
    """ 
    Two states with an interstate assignment in between, where the assigned
    value is used in the first state. Should fail.
    """
    sdfg = dace.SDFG('state_fusion_test')
    sdfg.add_array('A', [2], dace.int32)
    state1, state2, state3, state4 = tuple(sdfg.add_state() for _ in range(4))
    sdfg.add_edge(state1, state2, dace.InterstateEdge(assignments=dict(k=1)))
    sdfg.add_edge(state2, state3, dace.InterstateEdge())
    sdfg.add_edge(state3, state4, dace.InterstateEdge(assignments=dict(k=2)))

    state3.add_edge(state3.add_tasklet('one', {}, {'a'}, 'a = k'), 'a',
                    state3.add_write('A'), None, dace.Memlet('A[0]'))

    state4.add_edge(state3.add_tasklet('two', {}, {'a'}, 'a = k'), 'a',
                    state3.add_write('A'), None, dace.Memlet('A[1]'))

    try:
        StateFusion.apply_to(sdfg,
                             strict=True,
                             first_state=state3,
                             second_state=state4)
        raise AssertionError('States fused, test failed')
    except ValueError:
        print('Exception successfully caught')


# Connected components tests
def test_two_to_one_cc_fusion():
    """ Two states, first with two connected components, second with one. """
    sdfg = dace.SDFG('state_fusion_test')
    sdfg.add_array('A', [1], dace.int32)
    sdfg.add_array('B', [1], dace.int32)
    sdfg.add_array('C', [1], dace.int32)
    state1, state2 = tuple(sdfg.add_state() for _ in range(2))
    sdfg.add_edge(state1, state2, dace.InterstateEdge())

    # First state
    state1.add_edge(state1.add_tasklet('one', {}, {'a'}, 'a = 1'), 'a',
                    state1.add_write('A'), None, dace.Memlet('A'))

    t2 = state1.add_tasklet('two', {}, {'b', 'c'}, 'b = 2; c = 3')
    state1.add_edge(t2, 'b', state1.add_write('B'), None, dace.Memlet('B'))
    state1.add_edge(t2, 'c', state1.add_write('C'), None, dace.Memlet('C'))

    # Second state
    t2 = state2.add_tasklet('three', {'a', 'b', 'c'}, {'out'}, 'out = a+b+c')
    state2.add_edge(state2.add_read('A'), None, t2, 'a', dace.Memlet('A'))
    state2.add_edge(state2.add_read('B'), None, t2, 'b', dace.Memlet('B'))
    state2.add_edge(state2.add_read('C'), None, t2, 'c', dace.Memlet('C'))
    state2.add_edge(t2, 'out', state2.add_write('C'), None, dace.Memlet('C'))

    assert sdfg.apply_transformations_repeated(StateFusion, strict=True) == 1


def test_one_to_two_cc_fusion():
    """ Two states, first with one connected component, second with two. """
    sdfg = dace.SDFG('state_fusion_test')
    sdfg.add_array('A', [1], dace.int32)
    sdfg.add_array('B', [1], dace.int32)
    state1, state2 = tuple(sdfg.add_state() for _ in range(2))
    sdfg.add_edge(state1, state2, dace.InterstateEdge())

    # First state
    t1 = state1.add_tasklet('one', {}, {'a', 'b'}, 'a = 1; b = 2')
    state1.add_edge(t1, 'a', state1.add_write('A'), None, dace.Memlet('A'))
    state1.add_edge(t1, 'b', state1.add_write('B'), None, dace.Memlet('B'))

    # Second state
    state2.add_edge(state2.add_read('A'), None,
                    state2.add_tasklet('one', {'a'}, {}, ''), 'a',
                    dace.Memlet('A'))
    state2.add_edge(state2.add_read('B'), None,
                    state2.add_tasklet('two', {'b'}, {}, ''), 'b',
                    dace.Memlet('B'))

    assert sdfg.apply_transformations_repeated(StateFusion, strict=True) == 1


def test_two_cc_fusion_separate():
    """ Two states, both with two connected components, fused separately. """
    sdfg = dace.SDFG('state_fusion_test')
    sdfg.add_array('A', [1], dace.int32)
    sdfg.add_array('B', [1], dace.int32)
    sdfg.add_array('C', [1], dace.int32)
    state1, state2 = tuple(sdfg.add_state() for _ in range(2))
    sdfg.add_edge(state1, state2, dace.InterstateEdge())

    # First state
    state1.add_edge(state1.add_tasklet('one', {}, {'a'}, 'a = 1'), 'a',
                    state1.add_write('A'), None, dace.Memlet('A'))

    t2 = state1.add_tasklet('two', {}, {'b', 'c'}, 'b = 2; c = 3')
    state1.add_edge(t2, 'b', state1.add_write('B'), None, dace.Memlet('B'))
    state1.add_edge(t2, 'c', state1.add_write('C'), None, dace.Memlet('C'))

    # Second state
    state2.add_edge(state2.add_read('A'), None,
                    state2.add_tasklet('one', {'a'}, {}, ''), 'a',
                    dace.Memlet('A'))

    t2 = state2.add_tasklet('two', {'b', 'c'}, {}, '')
    state2.add_edge(state2.add_read('B'), None, t2, 'b', dace.Memlet('B'))
    state2.add_edge(state2.add_read('C'), None, t2, 'c', dace.Memlet('C'))

    assert sdfg.apply_transformations_repeated(StateFusion, strict=True) == 1


def test_two_cc_fusion_together():
    """ Two states, both with two connected components, fused to one CC. """
    sdfg = dace.SDFG('state_fusion_test')
    sdfg.add_array('A', [1], dace.int32)
    sdfg.add_array('B', [1], dace.int32)
    sdfg.add_array('C', [1], dace.int32)
    state1, state2 = tuple(sdfg.add_state() for _ in range(2))
    sdfg.add_edge(state1, state2, dace.InterstateEdge())

    # First state
    state1.add_edge(state1.add_tasklet('one', {}, {'a'}, 'a = 1'), 'a',
                    state1.add_write('A'), None, dace.Memlet('A'))

    t2 = state1.add_tasklet('two', {}, {'b', 'c'}, 'b = 2; c = 3')
    state1.add_edge(t2, 'b', state1.add_write('B'), None, dace.Memlet('B'))
    state1.add_edge(t2, 'c', state1.add_write('C'), None, dace.Memlet('C'))

    # Second state
    state2.add_edge(state2.add_read('B'), None,
                    state2.add_tasklet('one', {'a'}, {}, ''), 'a',
                    dace.Memlet('B'))

    t2 = state2.add_tasklet('two', {'b', 'c'}, {'d', 'e'}, 'd = b + c; e = b')
    state2.add_edge(state2.add_read('A'), None, t2, 'b', dace.Memlet('A'))
    state2.add_edge(state2.add_read('C'), None, t2, 'c', dace.Memlet('C'))
    state2.add_edge(t2, 'd', state2.add_write('A'), None, dace.Memlet('A'))
    state2.add_edge(t2, 'e', state2.add_write('C'), None, dace.Memlet('C'))

    assert sdfg.apply_transformations_repeated(StateFusion, strict=True) == 1


# Data race avoidance tests
def test_write_write_path():
    """
    Two states where both write to the same range of an array, but there is
    a path between the write and the second write.
    """
    @dace.program
    def state_fusion_test(A: dace.int32[20, 20]):
        A += 1
        tmp = A + 2
        A[:] = tmp + 3

    sdfg = state_fusion_test.to_sdfg(strict=False)
    sdfg.apply_transformations_repeated(StateFusion, strict=True)
    assert len(sdfg.nodes()) == 1


def test_write_write_no_overlap():
    """
    Two states where both write to different ranges of an array.
    """
    N = dace.symbol('N', positive=True)

    @dace.program
    def state_fusion_test(A: dace.int32[N, N]):
        A[0:N - 1, :] = 1
        A[N - 1, :] = 2

    sdfg = state_fusion_test.to_sdfg(strict=False)
    sdfg.apply_transformations_repeated(StateFusion, strict=True)
    assert len(sdfg.nodes()) == 1


def test_read_write_no_overlap():
    """
    Two states where two separate CCs write and read to/from an array, but
    in different ranges.
    """
    N = dace.symbol('N')

    @dace.program
    def state_fusion_test(A: dace.int32[N, N], B: dace.int32[N, N]):
        A[:, 5:N] = 1
        B[:, 3:6] = A[:, 0:3]

    sdfg = state_fusion_test.to_sdfg(strict=False)
    sdfg.apply_transformations_repeated(StateFusion, strict=True)
    assert len(sdfg.nodes()) == 1


if __name__ == '__main__':
    test_fuse_assignments()
    test_fuse_assignment_in_use()
    test_two_to_one_cc_fusion()
    test_one_to_two_cc_fusion()
    test_two_cc_fusion_separate()
    test_two_cc_fusion_together()
    test_write_write_path()
    test_write_write_no_overlap()
    test_read_write_no_overlap()
