"""Conditional joint glucose/adenylate inference; archived model stays untouched."""

import ast
import copy
import math
from pathlib import Path
import types
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp
from threadpoolctl import threadpool_limits

import equadiff_brodbar as kernel
from fla_profiled_observation_noise import profile_lognormal_dispersion
from rbc_distinct_volume_transport import glut_import, phase_matrix
from reaction_positivity import limit_signed_fluxes

POOLS = ("EGLC", "GLC", "LAC", "ELAC", "ATP", "ADP", "AMP")
GROUPS = {
    "investment": ("vmax_VHK", "vmax_VPFK"),
    "AK_capacity": ("vmax_VAK", "vmax_VAK_rev"),
    "GAPDH_PGK_capacity": ("vmax_VGAPDH", "vmax_VPGK"),
    "PK_capacity": ("vmax_VPK",),
    "PEP_PASE_capacity": ("vmax_VPEP_PASE",),
}
COORDINATES = ("GLUT_conductance", *GROUPS)


def scalar_mm(substrate, km, hill_coef=1.0):
    """Same scalar powers and boundary rule; scalar finite check avoids two ufuncs."""
    if substrate < 0:
        substrate = 0.0
    if km <= 0:
        km = kernel.MIN_KM
    try:
        result = substrate**hill_coef / (km**hill_coef + substrate**hill_coef)
        return result if math.isfinite(result) else 0.0
    except (ArithmeticError, ValueError, TypeError):
        return 0.0


@lru_cache(maxsize=2)
def compile_raw_rates(reactions):
    """Extract the existing rate prefix before pool balances, without rewriting rates.

    This is a trusted local-source transform, not execution of document content.
    All rate expressions/helper bodies are retained. Only scalar finite tests in
    mm are specialized; final candidates are audited with the original full RHS.
    """
    source = Path(kernel.__file__).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "equadiff_brodbar")
    prefix = []
    for node in function.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "dxdt"
            for t in node.targets
        ):
            break
        prefix.append(node)
    else:
        raise ValueError("native rate/balance boundary not found")
    assigned = {n.id for statement in prefix for n in ast.walk(statement)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    if not set(reactions) <= assigned:
        raise ValueError("native rate prefix does not span every reaction")
    function.body = prefix + [ast.Return(value=ast.Call(
        func=ast.Attribute(value=ast.Name(id="np", ctx=ast.Load()), attr="array", ctx=ast.Load()),
        args=[ast.List(elts=[ast.Name(id=r, ctx=ast.Load()) for r in reactions], ctx=ast.Load())], keywords=[]))]
    function.name = "_source_rates"
    function.decorator_list = []
    scope = dict(vars(kernel))
    # Clone helper globals, never monkey-patch the historical module.
    for name, value in vars(kernel).items():
        if isinstance(value, types.FunctionType) and value.__module__ == kernel.__name__:
            clone = types.FunctionType(value.__code__, scope, value.__name__, value.__defaults__, value.__closure__)
            clone.__kwdefaults__ = value.__kwdefaults__
            scope[name] = clone
    scope["mm"] = scalar_mm
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(Path(kernel.__file__).resolve()), "exec"), scope)
    return scope["_source_rates"]


@lru_cache(maxsize=2)
def rate_dependencies(reactions):
    """Conservative structural support from the executed local source AST.

    Whole-state helper arguments use all literal/global-index reads in all
    branches, including nested helpers. Unknown whole-state operations fall
    back to every column; this never infers sparsity from a few sampled zeros.
    """
    tree = ast.parse(Path(kernel.__file__).read_text(encoding="utf-8-sig"))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    all_columns = set(range(114))

    def index(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            value = vars(kernel).get(node.id)
            if isinstance(value, int):
                return value
        return None

    def vector_reads(node, vector, seen):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == vector:
            i = index(node.slice)
            return {i} if i is not None and 0 <= i < 114 else all_columns.copy()
        if isinstance(node, ast.Call):
            vectors = [i for i, a in enumerate(node.args) if isinstance(a, ast.Name) and a.id == vector]
            if vectors:
                if not isinstance(node.func, ast.Name) or node.func.id not in functions or node.func.id in seen:
                    return all_columns.copy()
                called = functions[node.func.id]
                result = set()
                for i in vectors:
                    if i >= len(called.args.args):
                        return all_columns.copy()
                    argument = called.args.args[i].arg
                    for statement in called.body:
                        result |= vector_reads(statement, argument, seen | {node.func.id})
                for a in [*node.args, *(k.value for k in node.keywords)]:
                    if not (isinstance(a, ast.Name) and a.id == vector):
                        result |= vector_reads(a, vector, seen)
                return result
        if isinstance(node, ast.Name) and node.id == vector and isinstance(node.ctx, ast.Load):
            return all_columns.copy()
        return set().union(*(vector_reads(n, vector, seen) for n in ast.iter_child_nodes(node)))

    env = {}

    def expression(node):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "x":
            i = index(node.slice)
            return {i} if i is not None and 0 <= i < 114 else all_columns.copy()
        if isinstance(node, ast.Call) and any(isinstance(a, ast.Name) and a.id == "x" for a in node.args):
            return vector_reads(node, "x", set()) | set().union(*(
                expression(a) for a in [*node.args, *(k.value for k in node.keywords)]
                if not (isinstance(a, ast.Name) and a.id == "x")))
        if isinstance(node, ast.Name):
            return all_columns.copy() if node.id == "x" else env.get(node.id, set()).copy()
        return set().union(*(expression(n) for n in ast.iter_child_nodes(node)))

    def statements(nodes, control=frozenset()):
        for node in nodes:
            if isinstance(node, ast.Assign):
                deps = expression(node.value) | set(control)
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id != "x":
                        env[target.id] = env.get(target.id, set()) | deps
            elif isinstance(node, ast.If):
                condition = set(control) | expression(node.test)
                statements(node.body, condition)
                statements(node.orelse, condition)
    prefix = []
    for node in functions["equadiff_brodbar"].body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                               and t.value.id == "dxdt" for t in node.targets):
            break
        prefix.append(node)
    statements(prefix)
    if not set(reactions) <= set(env):
        raise ValueError("unresolved raw-rate dependency")
    env["VEGLC"] = {0, 85}
    return tuple(frozenset(env[r]) for r in reactions)


class JointRHS:
    """One execution of the signed reaction vector, in fixed phase coordinates."""

    def __init__(self, parameters, kinetics, *, hematocrit=.58, threshold=.001):
        self.parameters, self.kinetics = copy.deepcopy(parameters), dict(kinetics)
        if any(str(v).startswith("teacher_curve") for k, v in self.parameters.items() if k.startswith("kinetic_family_")):
            raise ValueError("no teacher-forced kinetics in joint free inference")
        self.names, self.reactions, self.matrix, self.volumes, _ = phase_matrix(
            hematocrit, self.parameters.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
        if not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("fixed positive reaction availability threshold required")
        self.threshold = threshold
        self.raw_function = compile_raw_rates(self.reactions)
        self.glut_column = self.reactions.index("VEGLC")
        self.glucose_indices = [self.names.index(p) for p in ("GLC", "EGLC")]
        pattern = np.zeros((114,114), dtype=bool)
        for j, deps in enumerate(rate_dependencies(self.reactions)):
            rows = np.flatnonzero(self.matrix[:, j])
            # Either sign can consume either side; include every participating pool.
            columns = sorted(set(deps) | set(rows.tolist()))
            pattern[np.ix_(rows, columns)] = True
        self.jacobian_sparsity = pattern

    def rates(self, t, x):
        if np.shape(x) != (114,) or not np.all(np.isfinite(x)):
            raise ValueError("114 finite states required")
        raw = self.raw_function(t, x, custom_params=self.parameters, positivity_policy="reaction_consistent",
                                reaction_availability_threshold=self.threshold, curve_fit_strength=0.)
        gi, ge = (max(float(x[i]), 0.) for i in self.glucose_indices)
        raw[self.glut_column] = glut_import(gi, ge, **self.kinetics)
        executed, factors = limit_signed_fluxes(x[:113], raw, self.matrix, threshold=self.threshold)
        return raw, executed, factors

    def __call__(self, t, x):
        _, executed, _ = self.rates(t, x)
        d = np.r_[self.matrix @ executed, 0.]
        if not np.all(np.isfinite(d)) or np.max(np.abs(d[:113])) > kernel.MAX_DERIVATIVE:
            raise ValueError("invalid executed derivative; no clipping allowed")
        return d


def resolve_capacities(parameters):
    defaults = {}
    tree = ast.parse(Path(kernel.__file__).read_text(encoding="utf-8-sig"))
    requested = {p for group in GROUPS.values() for p in group}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_get_param" and len(node.args) == 3:
            key = node.args[1]
            if isinstance(key, ast.Constant) and key.value in requested:
                defaults[key.value] = ast.literal_eval(node.args[2])
    result = {p: parameters.get(p, defaults.get(p)) for p in requested}
    if any(v is None or not np.isfinite(v) or v <= 0 for v in result.values()):
        raise ValueError("every fitted capacity must have a positive native seed")
    return result


def unpack(log_factors, parameters, kinetics, capacities, bounds):
    x = np.asarray(log_factors, dtype=float)
    limits = np.log(np.asarray([bounds[n] for n in COORDINATES]))
    if x.shape != (len(COORDINATES),) or not np.all(np.isfinite(x)):
        raise ValueError("finite six-coordinate log vector required")
    if np.any(x < limits[:, 0]-1e-12) or np.any(x > limits[:, 1]+1e-12):
        raise ValueError("kinetic factor outside declared exploratory bounds")
    factors = dict(zip(COORDINATES, np.exp(x).tolist()))
    p, k = copy.deepcopy(parameters), dict(kinetics)
    k["conductance"] *= factors["GLUT_conductance"]
    for group, names in GROUPS.items():
        for name in names:
            p[name] = capacities[name] * factors[group]
    if p["vmax_VHK"] > 5.0+1e-12:
        raise ValueError("retained HK ceiling exceeded")
    return p, k, factors


def joint_score(predicted, observed):
    """One shared profiled relative dispersion, conditional independence explicit.

    The seven channels receive no free per-pool variance that could hide a failed
    adenylate. J1 and concentration-derived teachers are not extra likelihoods.
    """
    pred, obs = np.asarray(predicted, float), np.asarray(observed, float)
    if pred.ndim != 2 or pred.shape[0] != len(POOLS) or pred.shape != obs.shape or pred.shape[1] < 1:
        raise ValueError("seven aligned channels at actual noninitial source times required")
    result = profile_lognormal_dispersion(pred.ravel(), obs.ravel())
    result.update({"pools": list(POOLS), "points_per_pool": pred.shape[1],
        "log_RMSE": float(np.sqrt(np.mean(np.log(obs/pred)**2))),
        "per_pool_RMSE_mM": dict(zip(POOLS, np.sqrt(np.mean((pred-obs)**2, axis=1)).tolist())),
        "per_pool_log_RMSE": dict(zip(POOLS, np.sqrt(np.mean(np.log(obs/pred)**2, axis=1)).tolist())),
        "covariance_assumption": "conditional_independent_same_log_variance_not_estimated_assay_covariance",
        "assay_precision_known": False, "teachers_independent_likelihood_terms": False})
    return result


def predict(initial, parameters, kinetics, end_day, sample_time, *, profile=None):
    if np.shape(initial) != (114,) or initial[-1] != 7.2:
        raise ValueError("exact frozen114-state clamped-pH initialization required")
    times = np.asarray(sample_time, float)
    if times.ndim != 1 or len(times) == 0 or times[0] <= 1 or np.any(np.diff(times) <= 0) or times[-1] > end_day:
        raise ValueError("ordered actual post-J1 sample times within replay required")
    rhs = JointRHS(parameters, kinetics)
    options = {"rtol": 1e-7, "atol": 1e-9} if profile is None else profile
    with threadpool_limits(limits=1):
        sol = solve_ivp(rhs, (1., float(end_day)), initial.copy(), method="BDF", dense_output=True,
                        jac_sparsity=rhs.jacobian_sparsity, **options)
    if not sol.success or sol.t[-1] != end_day or not np.array_equal(sol.y[:, 0], initial):
        raise ValueError("incomplete or altered-initial-state free integration")
    dense = sol.sol(np.unique(np.r_[np.linspace(1., end_day, 301), times]))
    if min(sol.y[:113].min(), dense[:113].min()) < -1e-10:
        raise ValueError("negative checked concentration in fitting replay")
    prediction = sol.sol(times)[[rhs.names.index(p) for p in POOLS]]
    return prediction, sol, rhs
