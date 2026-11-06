"""Risk-Portfolio (Markowitz) allocation strategy across multimodal carriers.

Mathematical Formulation & Methodological Design:
------------------------------------------------
This module implements payload allocation across heterogeneous carriers (Image, Audio, Video)
inspired by Markowitz Modern Portfolio Theory (Mean-Variance Optimization):
1. In classical finance, an investor selects asset weights to minimize portfolio variance w^T Sigma w
   subject to a target return constraint.
2. In cross-modal steganography, the allocator distributes an encrypted payload envelope of B bytes
   across Image, Audio, and Video carriers: b = [b_I, b_A, b_V]^T.
3. The optimization objective balances risk variance minimization against capacity proportionality:
       minimize (1 - lambda) * V_norm(x) + lambda * D_norm(x)
       subject to sum(x_i) = 1,  0 <= x_i <= C_i / B
   where x = b / B is the normalized allocation fraction vector.

Objective Terms & Scaled Calibration:
------------------------------------
- V_norm(x) = (x^T Sigma x) / Tr(Sigma):
  Quadratic portfolio variance normalized by the trace of Sigma. Dividing by Tr(Sigma) ensures that
  the term is scale-invariant with respect to arbitrary scalar multipliers of the covariance matrix.
  Note: While Tr(Sigma) = sum(lambda_i) >= lambda_max(Sigma) for positive semi-definite matrices,
  V_norm(x) is mathematically bounded above by lambda_max / Tr(Sigma) <= 1 for unit L2 vectors,
  and for L1 simplex vectors (sum(x_i) = 1) its range is dictated by the cross-carrier covariance structure.
- D_norm(x) = 0.5 * ||x - w_cap||_2^2:
  Dimensionless Euclidean deviation from the proportional capacity distribution vector
  w_cap = [C_I / sum(C), C_A / sum(C), C_V / sum(C)]^T.
- lambda in [0.0, 1.0]: Dimensionless risk-tolerance parameter.
  * lambda = 0.0: Minimum-variance portfolio (maximizes stealth proxy, ignores capacity spread).
  * lambda = 1.0: Capacity-proportional allocation (minimizes deviation from carrier capacity share).
  * lambda in (0, 1): Calibrated trade-off between risk concentration and carrier balance.

Covariance Matrix & Regularization:
-----------------------------------
- Default: Diagonal heuristic covariance matrix derived from inverse complexity scores:
      Sigma_diag = diag(1 / CS_I^2, 1 / CS_A^2, 1 / CS_V^2)
  where CS_i in [0.05, 1.0] is the empirical perceptual complexity score from profiler.py.
  This matrix is strictly positive definite (all eigenvalues > 0).
- When an empirical covariance matrix is provided, it is symmetrized and regularized using
  strict eigenvalue flooring (spectral projection):
      Sigma_sym = 0.5 * (M + M^T)
      Sigma_PD = Q diag(max(lambda_i, epsilon)) Q^T
  where M_sym = Q Lambda Q^T is the orthogonal eigendecomposition.
  Any adjustment is explicitly tracked via `was_regularized` and `original_min_eigenvalue`.

Relative Risk & Efficient Frontier:
-----------------------------------
- Relative Risk Index in [0.0, 1.0]:
  Computed strictly over the feasible allocation polytope S(B) = {b in R^3 : sum(b_i) = B, 0 <= b_i <= C_i}:
      RelativeRisk(b) = (b^T Sigma b - V_min(B)) / (V_max(B) - V_min(B))
  where V_min(B) is the minimal variance solution at lambda = 0, and V_max(B) is the maximum variance
  evaluated over the extreme vertices of the feasible polytope S(B).
- Efficient Frontier:
  Represents the intrinsic minimum-variance curve F(B_k) = min_{b in S(B_k)} b^T Sigma b across discrete
  payload steps B_k in [0, C_total]. The slider lambda selects an allocation for a chosen payload B;
  it does NOT alter the frontier curve.

Scientific Limitations Notice:
------------------------------
Minimizing this quadratic proxy does NOT guarantee mathematical undetectability or immunity against
trained machine-learning steganalysis (e.g., SRM, deep neural network classifiers). The profiling
variance and complexity scores serve as relative rate-distortion proxies, not empirical proofs of stealth.
"""

from dataclasses import asdict, dataclass
import itertools
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.optimize import minimize

from app.allocation.allocator import (
    AllocationError,
    AllocationPlan,
    BaseAllocationStrategy,
    CarrierAllocation,
    MultimodalCapacityExceededError,
)
from app.allocation.strategies import (
    shared_clamp_and_redistribute,
    normalize_capacities,
    normalize_complexity_scores,
)
from app.allocation.profiler import MultimodalTriadProfile
from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE

# Modality order convention across all vector and matrix calculations
CARRIER_ORDER: Tuple[str, str, str] = ("image", "audio", "video")


@dataclass(frozen=True)
class CovarianceValidationResult:
    """Result of covariance matrix validation and spectral regularization.

    Attributes:
        matrix: Symmetric positive-definite matrix guaranteed for QP solvers.
        was_regularized: True if input had negative or near-zero eigenvalues or was asymmetric.
        original_min_eigenvalue: Smallest eigenvalue before spectral flooring.
        notes: Audit log describing adjustments made.
    """
    matrix: np.ndarray
    was_regularized: bool
    original_min_eigenvalue: float
    notes: str


@dataclass(frozen=True)
class EfficientFrontierPoint:
    """A discrete point along the Markowitz Efficient Frontier curve."""
    payload_bytes: int
    unnormalized_variance: float
    allocations: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload_bytes": self.payload_bytes,
            "unnormalized_variance": round(self.unnormalized_variance, 6),
            "allocations": self.allocations,
        }


def validate_and_regularize_covariance(
    matrix: np.ndarray,
    epsilon: float = 1e-6
) -> CovarianceValidationResult:
    """Validate and regularize a covariance matrix using exact eigenvalue flooring.

    Algorithm:
    1. Check dimensions (must be 3x3 square numeric matrix).
    2. Symmetrize: M_sym = 0.5 * (M + M^T).
    3. Compute orthogonal spectral decomposition: M_sym = Q Lambda Q^T using np.linalg.eigh.
    4. Record smallest eigenvalue original_min_eigenvalue.
    5. Floor eigenvalues: Lambda_floored = diag(max(lambda_i, epsilon)).
    6. Reconstruct: Sigma_PD = Q Lambda_floored Q^T.
    7. Re-symmetrize to eliminate any numerical reconstruction asymmetry.

    Args:
        matrix: 3x3 input array.
        epsilon: Minimum eigenvalue threshold.

    Returns:
        CovarianceValidationResult dataclass.
    """
    mat = np.asarray(matrix, dtype=np.float64)
    if mat.shape != (3, 3):
        raise ValueError(f"Covariance matrix must be shape (3, 3), got {mat.shape}")

    # Check asymmetry
    asym_norm = np.linalg.norm(mat - mat.T, ord=np.inf)
    was_asymmetric = asym_norm > 1e-8

    # Symmetrize
    mat_sym = 0.5 * (mat + mat.T)

    # Spectral decomposition
    eigenvalues, eigenvectors = np.linalg.eigh(mat_sym)
    original_min_eig = float(np.min(eigenvalues))

    needs_flooring = original_min_eig < epsilon

    if needs_flooring or was_asymmetric:
        floored_eigenvalues = np.maximum(eigenvalues, epsilon)
        mat_pd = eigenvectors @ np.diag(floored_eigenvalues) @ eigenvectors.T
        # Final cleanup for numerical precision
        mat_pd = 0.5 * (mat_pd + mat_pd.T)

        notes_parts = []
        if was_asymmetric:
            notes_parts.append(f"Input was asymmetric (max discrepancy: {asym_norm:.2e}). Symmetrized.")
        if needs_flooring:
            notes_parts.append(f"Smallest eigenvalue was {original_min_eig:.2e} < {epsilon:.2e}. Floored to epsilon.")
        notes = " ".join(notes_parts)
        was_regularized = True
    else:
        mat_pd = mat_sym
        was_regularized = False
        notes = "Matrix is symmetric and strictly positive-definite. No regularization needed."

    return CovarianceValidationResult(
        matrix=mat_pd,
        was_regularized=was_regularized,
        original_min_eigenvalue=original_min_eig,
        notes=notes,
    )


def build_default_diagonal_covariance(triad_profile: MultimodalTriadProfile) -> np.ndarray:
    """Build default diagonal risk covariance matrix from carrier complexity scores.

    Variance formula per carrier:
        sigma_i^2 = 1.0 / (ComplexityScore_i)^2

    Since ComplexityScore_i in [0.05, 1.0]:
        sigma_i^2 in [1.0, 400.0]
    High complexity (rich texture/motion) yields low variance (low penalty).
    Low complexity (flat sky/silence) yields high variance (high penalty).

    Args:
        triad_profile: Candidate cover carrier profile.

    Returns:
        3x3 diagonal NumPy array.
    """
    scores = {
        "image": max(0.05, float(triad_profile.image.complexity_score)),
        "audio": max(0.05, float(triad_profile.audio.complexity_score)),
        "video": max(0.05, float(triad_profile.video.complexity_score)),
    }
    variances = [1.0 / (scores[c] ** 2) for c in CARRIER_ORDER]
    return np.diag(variances)


def find_feasible_polytope_vertices(
    net_caps: Dict[str, int],
    payload_len: int
) -> List[np.ndarray]:
    """Find all extreme vertices of the feasible allocation polytope.

    The polytope is defined by:
        S(B) = { b in R^3 : b_I + b_A + b_V = B,  0 <= b_i <= C_i }

    For a 3D system with 1 equality and 6 box inequality constraints, the vertices
    correspond to greedy corner allocations: saturate carrier i, fill carrier j with remainder,
    leave carrier k empty, permuted across all permutations of (I, A, V).

    Args:
        net_caps: Mapping from carrier name to integer net capacity.
        payload_len: Total payload bytes B to distribute.

    Returns:
        List of distinct 3D vertex vectors in R^3.
    """
    caps = np.array([net_caps[c] for c in CARRIER_ORDER], dtype=np.float64)
    if payload_len == 0:
        return [np.zeros(3, dtype=np.float64)]

    vertices: List[np.ndarray] = []
    # Test all 3! = 6 fill orders
    for perm in itertools.permutations([0, 1, 2]):
        v = np.zeros(3, dtype=np.float64)
        rem = float(payload_len)
        for idx in perm:
            take = min(rem, caps[idx])
            v[idx] = take
            rem -= take
        if rem == 0.0:
            # Check if this vertex is unique (within numerical tolerance)
            if not any(np.allclose(v, existing, atol=1e-4) for existing in vertices):
                vertices.append(v)

    if not vertices:
        # Fallback to zero vector if payload exceeds capacity (should be caught earlier)
        return [np.zeros(3, dtype=np.float64)]

    return vertices


def compute_feasible_variance_bounds(
    net_caps: Dict[str, int],
    payload_len: int,
    sigma: np.ndarray,
    v_min: Optional[float] = None
) -> Tuple[float, float]:
    """Calculate the exact minimum and maximum portfolio variance over the feasible set.

    Args:
        net_caps: Net capacities for Image, Audio, Video.
        payload_len: Target payload length B.
        sigma: 3x3 positive-definite covariance matrix.
        v_min: Precomputed minimal variance from QP if available.

    Returns:
        (V_min, V_max) tuple of floats.
    """
    if payload_len == 0:
        return (0.0, 0.0)

    # 1. Compute V_max: Because b^T Sigma b is convex, its global maximum over
    # a compact convex polytope occurs at one of the extreme vertices.
    vertices = find_feasible_polytope_vertices(net_caps, payload_len)
    v_max = float(max(v @ sigma @ v for v in vertices))

    # 2. If V_min not provided, compute it via continuous QP solver at lambda=0
    if v_min is None:
        cont_b, _, _ = solve_portfolio_continuous(net_caps, payload_len, risk_tolerance=0.0, sigma=sigma)
        v_min = float(cont_b @ sigma @ cont_b)

    # Ensure v_max >= v_min numerically
    v_max = max(v_max, v_min)
    return (float(v_min), float(v_max))


def solve_portfolio_continuous(
    net_caps: Dict[str, int],
    payload_len: int,
    risk_tolerance: float,
    sigma: np.ndarray
) -> Tuple[np.ndarray, bool, str]:
    """Solve the continuous convex optimization problem in normalized space.

    Formulation:
        x = b / B
        minimize (1 - lambda) * V_norm(x) + lambda * D_norm(x)
        subject to sum(x) = 1,  0 <= x_i <= C_i / B

    Args:
        net_caps: Net capacities per carrier.
        payload_len: Target envelope payload B.
        risk_tolerance: lambda in [0.0, 1.0].
        sigma: Regularized 3x3 positive-definite covariance matrix.

    Returns:
        (continuous_b_array, solver_success, solver_message)
    """
    if payload_len == 0:
        return (np.zeros(3, dtype=np.float64), True, "Payload length is zero.")

    total_net = sum(net_caps.values())
    if payload_len > total_net:
        raise MultimodalCapacityExceededError(
            f"Payload of {payload_len} bytes exceeds combined net capacity {total_net} bytes."
        )

    # Trace normalization scalar
    tr_sigma = float(np.trace(sigma))
    if tr_sigma <= 0.0:
        tr_sigma = 1.0

    # Normalized capacity distribution target vector w_cap
    if total_net > 0:
        w_cap = np.array([net_caps[c] / total_net for c in CARRIER_ORDER], dtype=np.float64)
    else:
        w_cap = np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0], dtype=np.float64)

    # Bounds for x_i = b_i / B
    B_float = float(payload_len)
    bounds = []
    for c in CARRIER_ORDER:
        upper = min(1.0, float(net_caps[c]) / B_float)
        bounds.append((0.0, upper))

    # Objective function
    lam = float(np.clip(risk_tolerance, 0.0, 1.0))

    def objective(x: np.ndarray) -> float:
        # Term 1: Normalized variance
        v_norm = float(x @ sigma @ x) / tr_sigma
        # Term 2: Normalized capacity deviation
        d_norm = 0.5 * float(np.sum((x - w_cap) ** 2))
        return (1.0 - lam) * v_norm + lam * d_norm

    def objective_grad(x: np.ndarray) -> np.ndarray:
        grad_v = (2.0 * (sigma @ x)) / tr_sigma
        grad_d = x - w_cap
        return (1.0 - lam) * grad_v + lam * grad_d

    # Initial guess: capacity-proportional projection onto bounds
    x0 = np.clip(w_cap, [b[0] for b in bounds], [b[1] for b in bounds])
    if np.sum(x0) > 0:
        x0 = x0 / np.sum(x0)
    else:
        x0 = np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0])

    # Constraint: sum(x_i) == 1.0
    constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1.0, "jac": lambda x: np.ones(3)}]

    # Optimize using SLSQP
    res = minimize(
        objective,
        x0,
        jac=objective_grad,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 100, "disp": False},
    )

    if res.success:
        x_opt = np.clip(res.x, [b[0] for b in bounds], [b[1] for b in bounds])
        # Re-normalize to exact sum 1.0
        s = np.sum(x_opt)
        if s > 0:
            x_opt = x_opt / s
        b_cont = x_opt * B_float
        return (b_cont, True, str(res.message))
    else:
        # Fallback to capacity-proportional allocation
        b_fallback = np.array([min(float(net_caps[c]), w_cap[i] * B_float) for i, c in enumerate(CARRIER_ORDER)])
        rem = B_float - np.sum(b_fallback)
        if rem > 0:
            for i, c in enumerate(CARRIER_ORDER):
                room = float(net_caps[c]) - b_fallback[i]
                take = min(rem, room)
                b_fallback[i] += take
                rem -= take
        return (b_fallback, False, f"Optimization failed ({res.message}). Fell back to capacity proportional.")


def discretize_allocation(
    continuous_b: np.ndarray,
    net_caps: Dict[str, int],
    payload_len: int
) -> Dict[str, int]:
    """Convert continuous solution vector to exact integer bytes.

    Guarantees:
    1. sum(b_i) == payload_len exactly.
    2. 0 <= b_i <= net_caps[carrier] for all carriers.
    3. Deterministic tie-breaking using carrier index order (Image -> Audio -> Video).

    Args:
        continuous_b: 3D float array of continuous allocations in CARRIER_ORDER.
        net_caps: Net capacity mapping for each carrier.
        payload_len: Target integer payload B.

    Returns:
        Dictionary mapping carrier name ('image', 'audio', 'video') to integer bytes.
    """
    if payload_len == 0:
        return {c: 0 for c in CARRIER_ORDER}

    caps = [net_caps[c] for c in CARRIER_ORDER]
    floored: List[int] = [min(caps[i], max(0, int(math.floor(continuous_b[i])))) for i in range(3)]

    # Compute discrepancy
    deficit = payload_len - sum(floored)

    if deficit > 0:
        # Rank carriers by fractional part (b_cont - b_floor) descending, subject to headroom
        residuals = [
            (continuous_b[i] - floored[i], -i, i)  # -i ensures deterministic tie-breaking (0=I, 1=A, 2=V)
            for i in range(3)
            if floored[i] < caps[i]
        ]
        residuals.sort(reverse=True)

        for _, _, idx in residuals:
            if deficit == 0:
                break
            floored[idx] += 1
            deficit -= 1

        # If deficit remains (due to multiple carriers saturated), fill any remaining headroom deterministically
        if deficit > 0:
            for idx in range(3):
                headroom = caps[idx] - floored[idx]
                take = min(deficit, headroom)
                floored[idx] += take
                deficit -= take
                if deficit == 0:
                    break

    elif deficit < 0:
        # In rare numerical cases where floor sum exceeded payload (e.g. edge clamping)
        excess = -deficit
        residuals = [
            (continuous_b[i] - floored[i], i)
            for i in range(3)
            if floored[i] > 0
        ]
        residuals.sort()  # Smallest fractional parts reduced first
        for _, idx in residuals:
            if excess == 0:
                break
            take = min(excess, floored[idx])
            floored[idx] -= take
            excess -= take

    result = {CARRIER_ORDER[i]: floored[i] for i in range(3)}

    # Final assertion verification
    if sum(result.values()) != payload_len:
        raise AllocationError(
            f"Discretization internal error: allocated sum {sum(result.values())} != payload {payload_len}"
        )
    for c in CARRIER_ORDER:
        if result[c] > net_caps[c]:
            raise AllocationError(
                f"Discretization internal error: {c} allocated {result[c]} exceeds capacity {net_caps[c]}"
            )

    return result


def compute_efficient_frontier(
    triad_profile: MultimodalTriadProfile,
    num_points: int = 20,
    sigma: Optional[np.ndarray] = None
) -> List[EfficientFrontierPoint]:
    """Compute discrete Pareto-optimal points along the Markowitz Efficient Frontier.

    Calculates the minimum achievable portfolio variance for discrete payload levels B_k
    from 1 step up to total net capacity C_total.
    This frontier is an intrinsic physical property of the carrier profile and Sigma;
    it does NOT depend on or shift with the user's chosen risk_tolerance slider.

    Args:
        triad_profile: Profile of candidate cover carriers.
        num_points: Number of discrete frontier points (default 20).
        sigma: Optional custom covariance matrix. Defaults to diagonal heuristic.

    Returns:
        List of EfficientFrontierPoint instances.
    """
    net_caps = {
        "image": max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
        "audio": max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
        "video": max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
    }
    total_net = sum(net_caps.values())
    if total_net <= 0:
        return []

    cov_matrix = sigma if sigma is not None else build_default_diagonal_covariance(triad_profile)
    reg_res = validate_and_regularize_covariance(cov_matrix)
    sigma_pd = reg_res.matrix

    pts: List[EfficientFrontierPoint] = []
    # Always include 0 payload point
    pts.append(EfficientFrontierPoint(payload_bytes=0, unnormalized_variance=0.0, allocations={c: 0 for c in CARRIER_ORDER}))

    steps = max(2, min(50, num_points))
    step_size = max(1, total_net // steps)

    payload_levels = list(range(step_size, total_net, step_size))
    if not payload_levels or payload_levels[-1] != total_net:
        payload_levels.append(total_net)

    for B_step in payload_levels:
        cont_b, _, _ = solve_portfolio_continuous(net_caps, B_step, risk_tolerance=0.0, sigma=sigma_pd)
        disc = discretize_allocation(cont_b, net_caps, B_step)
        b_vec = np.array([disc[c] for c in CARRIER_ORDER], dtype=np.float64)
        var = float(b_vec @ sigma_pd @ b_vec)
        pts.append(EfficientFrontierPoint(payload_bytes=B_step, unnormalized_variance=var, allocations=disc))

    return pts


class RiskPortfolioStrategy(BaseAllocationStrategy):
    """Markowitz Risk-Portfolio multimodal allocation strategy.

    Implements constrained quadratic programming to minimize cross-carrier variance
    and balance capacity utilization.

    Attributes:
        risk_tolerance: Dimensionless parameter lambda in [0.0, 1.0].
        covariance_matrix: Optional custom 3x3 covariance matrix. Defaults to diagonal heuristic.
    """

    def __init__(
        self,
        risk_tolerance: float = 0.5,
        covariance_matrix: Optional[np.ndarray] = None
    ) -> None:
        self._risk_tolerance = float(np.clip(risk_tolerance, 0.0, 1.0))
        self._custom_covariance = covariance_matrix
        self.last_validation_result: Optional[CovarianceValidationResult] = None
        self.last_relative_risk: Optional[float] = None
        self.last_raw_variance: Optional[float] = None
        self.last_v_min: Optional[float] = None
        self.last_v_max: Optional[float] = None

    @property
    def strategy_name(self) -> str:
        return "portfolio"

    @property
    def risk_tolerance(self) -> float:
        return self._risk_tolerance

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Union[AllocationPlan, List[int]]:
        """Compute exact risk-minimized byte allocation across Image, Audio, and Video.

        Supports two interfaces:
        1. Full plan interface: allocate(payload_len, triad_profile, weights_config=None) -> AllocationPlan
        2. Common raw interface: allocate(B, capacities, features=None) -> List[int]
        """
        # Common raw interface: allocate(B, capacities, features=None) -> [b_I, b_A, b_V]
        if not (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) and "triad_profile" not in kwargs:
            B = int(args[0]) if args else int(kwargs.get("B", 0))
            if B < 0:
                raise AllocationError(f"Payload length cannot be negative: {B}")
            capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
            features = args[2] if len(args) > 2 else kwargs.get("features", None)

            caps = normalize_capacities(capacities)
            dict_caps = {"image": caps[0], "audio": caps[1], "video": caps[2]}

            if self._custom_covariance is not None:
                cov_raw = self._custom_covariance
            elif isinstance(features, dict) and "covariance_matrix" in features:
                cov_raw = np.asarray(features["covariance_matrix"], dtype=np.float64)
            else:
                cs = normalize_complexity_scores(features)
                cov_raw = np.diag([1.0 / (c ** 2) for c in cs])

            val_result = validate_and_regularize_covariance(cov_raw)
            sigma = val_result.matrix

            risk_tol = self._risk_tolerance
            if isinstance(features, dict):
                if "risk_tolerance" in features:
                    risk_tol = float(np.clip(features["risk_tolerance"], 0.0, 1.0))
                elif "lambda" in features:
                    risk_tol = float(np.clip(features["lambda"], 0.0, 1.0))
            if "risk_tolerance" in kwargs:
                risk_tol = float(np.clip(kwargs["risk_tolerance"], 0.0, 1.0))

            cont_b, _, _ = solve_portfolio_continuous(dict_caps, B, risk_tol, sigma)
            return shared_clamp_and_redistribute(cont_b.tolist(), B, caps)

        payload_len = int(args[0]) if args else int(kwargs["payload_len"])
        triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
        weights_config: Optional[Dict[str, float]] = args[2] if len(args) > 2 else kwargs.get("weights_config", None)
        # Determine risk tolerance (allow overrides from weights_config)
        risk_tol = self._risk_tolerance
        if weights_config:
            if "risk_tolerance" in weights_config:
                risk_tol = float(np.clip(weights_config["risk_tolerance"], 0.0, 1.0))
            elif "lambda" in weights_config:
                risk_tol = float(np.clip(weights_config["lambda"], 0.0, 1.0))

        usable_caps = {
            "image": triad_profile.image.max_usable_payload_bytes,
            "audio": triad_profile.audio.max_usable_payload_bytes,
            "video": triad_profile.video.max_usable_payload_bytes,
        }
        net_caps = {
            k: max(0, cap - ASTG_HEADER_SIZE) for k, cap in usable_caps.items()
        }
        total_net_cap = sum(net_caps.values())
        total_usable_cap = sum(usable_caps.values())

        if payload_len > total_net_cap:
            raise MultimodalCapacityExceededError(
                f"Payload of {payload_len} bytes exceeds combined net multimodal capacity "
                f"({total_net_cap} bytes across Image: {net_caps['image']}, "
                f"Audio: {net_caps['audio']}, Video: {net_caps['video']} after accounting for "
                f"3 x {ASTG_HEADER_SIZE}B ASTG packet headers)."
            )

        # 1. Build and validate covariance matrix
        if self._custom_covariance is not None:
            cov_raw = self._custom_covariance
        else:
            cov_raw = build_default_diagonal_covariance(triad_profile)

        val_result = validate_and_regularize_covariance(cov_raw)
        sigma = val_result.matrix

        # 2. Continuous Quadratic Optimization
        cont_b, solver_ok, solver_msg = solve_portfolio_continuous(
            net_caps=net_caps,
            payload_len=payload_len,
            risk_tolerance=risk_tol,
            sigma=sigma,
        )

        # 3. Discretization with exact byte conservation
        allocated = discretize_allocation(cont_b, net_caps, payload_len)

        # 4. Compute unnormalized variance and feasible relative risk index
        b_vec = np.array([allocated[c] for c in CARRIER_ORDER], dtype=np.float64)
        raw_variance = float(b_vec @ sigma @ b_vec)

        v_min, v_max = compute_feasible_variance_bounds(net_caps, payload_len, sigma)
        if v_max > v_min:
            relative_risk = float(np.clip((raw_variance - v_min) / (v_max - v_min), 0.0, 1.0))
        else:
            relative_risk = 0.0

        # Store calculation state for testing and transparency
        self.last_validation_result = val_result
        self.last_relative_risk = relative_risk
        self.last_raw_variance = raw_variance
        self.last_v_min = v_min
        self.last_v_max = v_max

        # Build detailed allocation report
        allocations: Dict[str, CarrierAllocation] = {}
        slice_offsets: Dict[str, Tuple[int, int]] = {}
        curr_offset = 0

        complexity_scores = {
            "image": triad_profile.image.complexity_score,
            "audio": triad_profile.audio.complexity_score,
            "video": triad_profile.video.complexity_score,
        }

        reg_note = " [Covariance regularized via eigenvalue flooring]" if val_result.was_regularized else ""

        for c in CARRIER_ORDER:
            bytes_assigned = allocated[c]
            overhead = ASTG_HEADER_SIZE if bytes_assigned > 0 else 0
            total_carrier_bytes = bytes_assigned + overhead
            usable_cap = usable_caps[c]
            net_cap = net_caps[c]
            util = round(total_carrier_bytes / usable_cap, 4) if usable_cap > 0 else 0.0

            slice_offsets[c] = (curr_offset, curr_offset + bytes_assigned)
            curr_offset += bytes_assigned

            pct = round((bytes_assigned / payload_len) * 100, 1) if payload_len > 0 else 0.0
            allocations[c] = CarrierAllocation(
                carrier_type=c,
                payload_bytes=bytes_assigned,
                chunk_overhead_bytes=overhead,
                total_carrier_payload_bytes=total_carrier_bytes,
                carrier_usable_capacity_bytes=usable_cap,
                carrier_net_capacity_bytes=net_cap,
                utilization_ratio=util,
                complexity_score=complexity_scores[c],
                weight=round(float(b_vec[CARRIER_ORDER.index(c)] / payload_len), 3) if payload_len > 0 else 0.0,
                reason=(
                    f"Assigned {bytes_assigned}B ({pct}% of payload): Markowitz portfolio QP solution "
                    f"at risk tolerance lambda={risk_tol:.2f} (continuous solution: {cont_b[CARRIER_ORDER.index(c)]:.1f}B).{reg_note}"
                ),
            )

        overall_util = round(
            sum(a.total_carrier_payload_bytes for a in allocations.values()) / total_usable_cap, 4
        ) if total_usable_cap > 0 else 0.0

        # 5. Compute Efficient Frontier and Matched Comparison Points on Identical Inputs
        frontier_pts = compute_efficient_frontier(triad_profile, num_points=12, sigma=sigma)
        comparison_points: Dict[str, Any] = {}
        if payload_len > 0:
            try:
                from app.allocation.allocator import FixedBaselineStrategy, AdaptiveFeatureStrategy
                fixed_plan = FixedBaselineStrategy().allocate(payload_len, triad_profile)
                adaptive_plan = AdaptiveFeatureStrategy().allocate(payload_len, triad_profile)

                b_fix = np.array([fixed_plan.allocations[c].payload_bytes for c in CARRIER_ORDER], dtype=np.float64)
                b_adp = np.array([adaptive_plan.allocations[c].payload_bytes for c in CARRIER_ORDER], dtype=np.float64)

                var_fix = float(b_fix @ sigma @ b_fix)
                var_adp = float(b_adp @ sigma @ b_adp)

                denom = v_max - v_min if v_max > v_min else 1.0
                rr_fix = float(np.clip((var_fix - v_min) / denom, 0.0, 1.0)) if v_max > v_min else 0.0
                rr_adp = float(np.clip((var_adp - v_min) / denom, 0.0, 1.0)) if v_max > v_min else 0.0

                comparison_points["fixed"] = {
                    "strategy": "fixed",
                    "allocations": {c: fixed_plan.allocations[c].payload_bytes for c in CARRIER_ORDER},
                    "unnormalized_variance": round(var_fix, 4),
                    "relative_risk": round(rr_fix, 4),
                }
                comparison_points["adaptive"] = {
                    "strategy": "adaptive",
                    "allocations": {c: adaptive_plan.allocations[c].payload_bytes for c in CARRIER_ORDER},
                    "unnormalized_variance": round(var_adp, 4),
                    "relative_risk": round(rr_adp, 4),
                }
            except Exception:
                pass

        portfolio_metadata: Dict[str, Any] = {
            "risk_tolerance": risk_tol,
            "relative_risk": round(relative_risk, 4),
            "unnormalized_variance": round(raw_variance, 4),
            "v_min": round(v_min, 4),
            "v_max": round(v_max, 4),
            "covariance_matrix": [[round(float(sigma[i, j]), 4) for j in range(3)] for i in range(3)],
            "carrier_names": list(CARRIER_ORDER),
            "was_regularized": val_result.was_regularized,
            "original_min_eigenvalue": round(val_result.original_min_eigenvalue, 6),
            "notes": val_result.notes,
            "efficient_frontier": [pt.to_dict() for pt in frontier_pts],
            "comparison_points": comparison_points,
        }

        plan = AllocationPlan(
            strategy_name=self.strategy_name,
            total_payload_bytes=payload_len,
            total_usable_capacity_bytes=total_usable_cap,
            total_net_capacity_bytes=total_net_cap,
            overall_utilization_ratio=overall_util,
            allocations=allocations,
            slice_offsets=slice_offsets,
            portfolio_metadata=portfolio_metadata,
        )

        return plan
