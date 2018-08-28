from fractions import Fraction

import numpy as np
import sympy as sp
import scipy.linalg as la

from fsc.export import export

from ._orbitals import Spin
from ._spin_reps import _spin_reps
from ._expr_utils import _get_substitution, _expr_to_vector


@export
def get_repr_matrix(
    *, orbitals, real_space_operator, rotation_matrix_cartesian, numeric=False
):
    orbitals = list(orbitals)

    positions_mapping = _get_positions_mapping(
        orbitals=orbitals, real_space_operator=real_space_operator
    )
    repr_matrix = sp.zeros(len(orbitals))

    expr_substitution = _get_substitution(rotation_matrix_cartesian)
    for i, orb in enumerate(orbitals):
        res_pos_idx = positions_mapping[i]
        spin_res = _apply_spin_rotation(
            rotation_matrix_cartesian=rotation_matrix_cartesian, spin=orb.spin
        )

        new_func = orb.function.subs(expr_substitution, simultaneous=True)
        for new_spin, spin_value in spin_res.items():
            res_pos_idx_reduced = [
                idx for idx in res_pos_idx if orbitals[idx].spin == new_spin
            ]
            func_basis_reduced = [
                orbitals[idx].function for idx in res_pos_idx_reduced
            ]
            func_vec = _expr_to_vector(
                new_func, basis=func_basis_reduced, numeric=numeric
            )
            func_vec_norm = la.norm(np.array(func_vec).astype(complex))
            if not np.isclose(func_vec_norm, 1):
                raise ValueError(
                    'Norm {} of vector {} for expression {} created from orbital {} is not one.\nCartesian rotation matrix: {}'.
                    format(
                        func_vec_norm, func_vec, new_func, orb,
                        rotation_matrix_cartesian
                    )
                )
            for idx, func_value in zip(res_pos_idx_reduced, func_vec):
                repr_matrix[idx, i] += func_value * spin_value
    # check that the matrix is unitary
    repr_matrix_numeric = np.array(repr_matrix).astype(complex)
    if not np.allclose(
        repr_matrix_numeric @ repr_matrix_numeric.conj().T,
        np.eye(*repr_matrix_numeric.shape)
    ):
        max_mismatch = np.max(
            np.abs(
                repr_matrix_numeric @ repr_matrix_numeric.conj().T -
                np.eye(*repr_matrix_numeric.shape)
            )
        )
        raise ValueError(
            'Representation matrix is not unitary. Maximum mismatch to unity: {}'.
            format(max_mismatch)
        )
    if numeric:
        return repr_matrix_numeric
    else:
        return repr_matrix


def _get_positions_mapping(orbitals, real_space_operator):
    positions = [orbital.position for orbital in orbitals]
    res = {}
    for i, pos1 in enumerate(positions):
        new_pos = real_space_operator.apply(pos1)
        res[i] = [
            j for j, pos2 in enumerate(positions)
            if _is_same_position(new_pos, pos2)
        ]
    return res


def _is_same_position(pos1, pos2):
    return np.isclose(_pos_distance(pos1, pos2), 0, atol=1e-6)


def _pos_distance(pos1, pos2):
    delta = np.array(pos1) - np.array(pos2)
    delta %= 1
    return la.norm(np.minimum(delta, 1 - delta))


def _apply_spin_rotation(rotation_matrix_cartesian, spin):
    if spin.total == 0:
        return {spin: 1}
    elif spin.total == Fraction(1, 2):
        spin_vec = _spin_to_vector(spin)
        spin_vec_res = _spin_reps(rotation_matrix_cartesian) @ spin_vec
        return _vec_to_spins(spin_vec_res)
    else:
        raise NotImplementedError('Spins larger than 1/2 are not implemented.')


def _spin_to_vector(spin):
    size = int(2 * spin.total + 1)
    idx = int(spin.total - spin.z_component)
    res = np.zeros(size)
    res[idx] = 1
    return res


def _vec_to_spins(vec):
    total = Fraction(vec.size - 1, 2)
    res = {}
    for i, val in enumerate(vec):
        if val != 0:
            res[Spin(total=total, z_component=total - i)] = val
    return res