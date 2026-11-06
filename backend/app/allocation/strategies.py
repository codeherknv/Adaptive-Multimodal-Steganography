"""New cross-modal steganography allocation strategies and common interface utilities.

This module implements:
1. `shared_clamp_and_redistribute`: Shared deterministic final allocation step
   applying capacity clamping, proportional overflow redistribution, and integer rounding
   to guarantee sum(b_i) == B exactly with zero capacity violations.
2. Five new allocation strategies:
   - CapacityProportionalStrategy (b_i proportional to C_i)
   - SquareRootLawStrategy (b_i proportional to sqrt(C_i))
   - RandomKeySeededStrategy (pseudo-random split with fixed seed)
   - MaxComplexityGreedyStrategy (greedy filling of highest complexity carrier first)
   - MinimaxRiskStrategy (minimize maximum per-carrier risk)
"""

from abc import ABC, abstractmethod
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.optimize import minimize

from app.allocation.profiler import MultimodalTriadProfile
from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE

# Modality order convention
CARRIER_ORDER: Tuple[str, str, str] = ("image", "audio", "video")


class AllocationError(Exception):
    """Base exception for allocation failures."""
    pass


class MultimodalCapacityExceededError(AllocationError):
    """Raised when payload exceeds total usable capacity."""
    pass


def normalize_capacities(capacities: Union[Sequence[int], Dict[str, int]]) -> List[int]:
    """Normalize input capacities to a 3-element list [C_I, C_A, C_V]."""
    if isinstance(capacities, dict):
        return [
            int(capacities.get("image", 0)),
            int(capacities.get("audio", 0)),
            int(capacities.get("video", 0)),
        ]
    caps = [int(c) for c in capacities]
    if len(caps) < 3:
        caps = caps + [0] * (3 - len(caps))
    return caps[:3]


def normalize_complexity_scores(
    features: Optional[Union[Dict[str, Any], Sequence[float]]]
) -> List[float]:
    """Extract 3 complexity scores [cs_I, cs_A, cs_V] in [0.05, 1.0] from features."""
    if features is None:
        return [0.5, 0.5, 0.5]
    if isinstance(features, (list, tuple)):
        scores = [float(x) for x in features[:3]]
        if len(scores) < 3:
            scores = scores + [0.5] * (3 - len(scores))
        return [max(0.05, min(1.0, s)) for s in scores]
    if isinstance(features, dict):
        if "complexity_scores" in features:
            cs = features["complexity_scores"]
            if isinstance(cs, dict):
                return [
                    max(0.05, min(1.0, float(cs.get("image", 0.5)))),
                    max(0.05, min(1.0, float(cs.get("audio", 0.5)))),
                    max(0.05, min(1.0, float(cs.get("video", 0.5)))),
                ]
            if isinstance(cs, (list, tuple)):
                return [max(0.05, min(1.0, float(x))) for x in cs[:3]]
        scores = []
        for c in CARRIER_ORDER:
            val = features.get(c, 0.5)
            if isinstance(val, dict):
                val = val.get("complexity_score", 0.5)
            scores.append(max(0.05, min(1.0, float(val))))
        return scores
    return [0.5, 0.5, 0.5]


def shared_clamp_and_redistribute(
    raw_shares: Sequence[float],
    B: int,
    capacities: Union[Sequence[int], Dict[str, int]]
) -> List[int]:
    """Shared deterministic final step applied to EVERY allocation strategy.

    Guarantees:
    1. Rejects negative B (raises AllocationError).
    2. Rejects B > sum(capacities) cleanly (raises MultimodalCapacityExceededError).
    3. If B == 0, returns [0, 0, 0].
    4. Continuous water-filling: clamps saturated carriers to their capacity C_i,
       redistributes excess payload proportionally to active unconstrained carriers.
    5. Integer rounding (Hamilton-Apportionment / largest remainder method) with
       deterministic tie-breaking order (Image -> Audio -> Video).
    6. Post-conditions guaranteed:
       - sum(b_i) == B exactly
       - 0 <= b_i <= C_i for all i
       - integer return values

    Args:
        raw_shares: Unconstrained weights or raw allocations [r_I, r_A, r_V].
        B: Total target payload bytes to allocate.
        capacities: Sequence or dict of carrier capacities [C_I, C_A, C_V].

    Returns:
        Exact integer byte allocation list [b_I, b_A, b_V].
    """
    if B < 0:
        raise AllocationError(f"Payload length B cannot be negative: {B}")

    caps = normalize_capacities(capacities)
    for i, c in enumerate(caps):
        if c < 0:
            raise AllocationError(f"Carrier capacity cannot be negative: capacity[{i}] = {c}")

    total_cap = sum(caps)
    if B > total_cap:
        raise MultimodalCapacityExceededError(
            f"Payload of {B} bytes exceeds combined net capacity ({total_cap} bytes: {caps})."
        )

    if B == 0:
        return [0] * len(caps)

    n = len(caps)
    # Ensure raw_shares has length n
    shares = [float(s) for s in raw_shares] if raw_shares else [1.0] * n
    if len(shares) < n:
        shares = shares + [1.0] * (n - len(shares))
    shares = shares[:n]

    # If all weights non-positive, fallback to capacity-proportional
    if sum(max(0.0, s) for s in shares) <= 0.0:
        shares = [float(c) for c in caps]

    # 1. Continuous water-filling with capacity bounds [0, C_i]
    allocated = [0.0] * n
    unallocated = float(B)
    active_indices = [i for i in range(n) if caps[i] > 0]
    weights = [max(0.0, shares[i]) for i in range(n)]

    while unallocated > 1e-9 and active_indices:
        sum_w = sum(weights[i] for i in active_indices)
        if sum_w <= 1e-12:
            # Distribute equally among active carriers
            equal_share = unallocated / len(active_indices)
            proportions = {i: equal_share for i in active_indices}
        else:
            proportions = {i: (weights[i] / sum_w) * unallocated for i in active_indices}

        clamped_any = False
        for i in list(active_indices):
            tentative = allocated[i] + proportions[i]
            if tentative >= caps[i] - 1e-9:
                delta = caps[i] - allocated[i]
                allocated[i] = float(caps[i])
                unallocated -= delta
                active_indices.remove(i)
                clamped_any = True

        if not clamped_any:
            for i in active_indices:
                allocated[i] += proportions[i]
            unallocated = 0.0
            break

    # 2. Largest-Remainder (Hamilton) Integer Discretization
    floored = [min(caps[i], max(0, int(math.floor(allocated[i])))) for i in range(n)]
    deficit = B - sum(floored)

    if deficit > 0:
        # Sort eligible carriers by fractional part descending
        # Secondary key -i ensures deterministic tie-breaking (0=I, 1=A, 2=V)
        residuals = [
            (allocated[i] - floored[i], -i, i)
            for i in range(n)
            if floored[i] < caps[i]
        ]
        residuals.sort(reverse=True)

        for _, _, idx in residuals:
            if deficit == 0:
                break
            floored[idx] += 1
            deficit -= 1

        # Catch remaining deficit if all fractional candidates saturated
        if deficit > 0:
            for idx in range(n):
                headroom = caps[idx] - floored[idx]
                take = min(deficit, headroom)
                floored[idx] += take
                deficit -= take
                if deficit == 0:
                    break

    elif deficit < 0:
        excess = -deficit
        residuals = [
            (allocated[i] - floored[i], i)
            for i in range(n)
            if floored[i] > 0
        ]
        residuals.sort()
        for _, idx in residuals:
            if excess == 0:
                break
            take = min(excess, floored[idx])
            floored[idx] -= take
            excess -= take

    # Invariant assertions
    if sum(floored) != B:
        raise AllocationError(
            f"Internal allocation error: sum(floored)={sum(floored)} != target B={B}"
        )
    for i in range(n):
        if floored[i] > caps[i]:
            raise AllocationError(
                f"Internal allocation error: carrier {i} allocated {floored[i]} > capacity {caps[i]}"
            )
        if floored[i] < 0:
            raise AllocationError(
                f"Internal allocation error: carrier {i} allocated negative {floored[i]}"
            )

    return floored


def build_plan_from_bytes(
    strategy_name: str,
    bytes_list: List[int],
    payload_len: int,
    triad_profile: MultimodalTriadProfile,
    weights_dict: Optional[Dict[str, float]] = None,
    portfolio_metadata: Optional[Dict[str, Any]] = None,
) -> Any:
    """Helper to wrap [b_I, b_A, b_V] into a full AllocationPlan."""
    from app.allocation.allocator import AllocationPlan, CarrierAllocation

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

    complexity_scores = {
        "image": triad_profile.image.complexity_score,
        "audio": triad_profile.audio.complexity_score,
        "video": triad_profile.video.complexity_score,
    }

    allocations: Dict[str, CarrierAllocation] = {}
    slice_offsets: Dict[str, Tuple[int, int]] = {}
    curr_offset = 0

    for i, c in enumerate(CARRIER_ORDER):
        bytes_assigned = bytes_list[i]
        overhead = ASTG_HEADER_SIZE if bytes_assigned > 0 else 0
        total_carrier_bytes = bytes_assigned + overhead
        usable_cap = usable_caps[c]
        net_cap = net_caps[c]
        util = round(total_carrier_bytes / usable_cap, 4) if usable_cap > 0 else 0.0

        slice_offsets[c] = (curr_offset, curr_offset + bytes_assigned)
        curr_offset += bytes_assigned

        pct = round((bytes_assigned / payload_len) * 100, 1) if payload_len > 0 else 0.0
        w = round(weights_dict.get(c, 1.0), 3) if weights_dict else 1.0

        allocations[c] = CarrierAllocation(
            carrier_type=c,
            payload_bytes=bytes_assigned,
            chunk_overhead_bytes=overhead,
            total_carrier_payload_bytes=total_carrier_bytes,
            carrier_usable_capacity_bytes=usable_cap,
            carrier_net_capacity_bytes=net_cap,
            utilization_ratio=util,
            complexity_score=complexity_scores[c],
            weight=w,
            reason=f"Assigned {bytes_assigned}B ({pct}% of payload) by {strategy_name} strategy.",
        )

    overall_util = round(
        sum(a.total_carrier_payload_bytes for a in allocations.values()) / total_usable_cap, 4
    ) if total_usable_cap > 0 else 0.0

    return AllocationPlan(
        strategy_name=strategy_name,
        total_payload_bytes=payload_len,
        total_usable_capacity_bytes=total_usable_cap,
        total_net_capacity_bytes=total_net_cap,
        overall_utilization_ratio=overall_util,
        allocations=allocations,
        slice_offsets=slice_offsets,
        portfolio_metadata=portfolio_metadata,
    )


# =====================================================================
# Strategy Implementations
# =====================================================================

class CapacityProportionalStrategy:
    """Allocates payload strictly proportional to carrier net capacity (b_i proportional to C_i)."""

    @property
    def strategy_name(self) -> str:
        return "capacity_proportional"

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        if (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) or "triad_profile" in kwargs:
            payload_len = int(args[0]) if args else int(kwargs["payload_len"])
            triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
            caps = [
                max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            ]
            raw_shares = [float(c) for c in caps]
            b_list = shared_clamp_and_redistribute(raw_shares, payload_len, caps)
            weights = {CARRIER_ORDER[i]: (caps[i] / sum(caps)) if sum(caps) > 0 else 0.0 for i in range(3)}
            return build_plan_from_bytes(self.strategy_name, b_list, payload_len, triad_profile, weights)

        # Standard tuple interface: allocate(B, capacities, features=None)
        B = int(args[0]) if args else int(kwargs.get("B", 0))
        capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
        caps = normalize_capacities(capacities)
        raw_shares = [float(c) for c in caps]
        return shared_clamp_and_redistribute(raw_shares, B, caps)


class SquareRootLawStrategy:
    """Allocates payload proportional to the square root of carrier capacity (b_i proportional to sqrt(C_i)).

    Based on Ker's Square Root Law of Steganographic Capacity.
    """

    @property
    def strategy_name(self) -> str:
        return "square_root_law"

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        if (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) or "triad_profile" in kwargs:
            payload_len = int(args[0]) if args else int(kwargs["payload_len"])
            triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
            caps = [
                max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            ]
            raw_shares = [math.sqrt(max(0, c)) for c in caps]
            b_list = shared_clamp_and_redistribute(raw_shares, payload_len, caps)
            sq_sum = sum(raw_shares)
            weights = {CARRIER_ORDER[i]: (raw_shares[i] / sq_sum) if sq_sum > 0 else 0.0 for i in range(3)}
            return build_plan_from_bytes(self.strategy_name, b_list, payload_len, triad_profile, weights)

        B = int(args[0]) if args else int(kwargs.get("B", 0))
        capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
        caps = normalize_capacities(capacities)
        raw_shares = [math.sqrt(max(0, c)) for c in caps]
        return shared_clamp_and_redistribute(raw_shares, B, caps)


class RandomKeySeededStrategy:
    """Allocates payload using a deterministic pseudo-random key-seeded split.

    Uses a fixed cryptographic or PRNG seed to sample random Dirichlet/uniform shares,
    respecting capacity bounds through the shared final step.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)

    @property
    def strategy_name(self) -> str:
        return "random_key_seeded"

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        seed = self.seed
        if "seed" in kwargs:
            seed = int(kwargs["seed"])

        if (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) or "triad_profile" in kwargs:
            payload_len = int(args[0]) if args else int(kwargs["payload_len"])
            triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
            weights_cfg = args[2] if len(args) > 2 else kwargs.get("weights_config", {})
            if weights_cfg and "seed" in weights_cfg:
                seed = int(weights_cfg["seed"])

            caps = [
                max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            ]
            rng = np.random.default_rng(seed)
            raw_shares = rng.uniform(0.1, 1.0, size=3).tolist()
            b_list = shared_clamp_and_redistribute(raw_shares, payload_len, caps)
            s_sum = sum(raw_shares)
            weights = {CARRIER_ORDER[i]: raw_shares[i] / s_sum for i in range(3)}
            return build_plan_from_bytes(self.strategy_name, b_list, payload_len, triad_profile, weights)

        B = int(args[0]) if args else int(kwargs.get("B", 0))
        capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
        features = args[2] if len(args) > 2 else kwargs.get("features", None)
        if isinstance(features, dict) and "seed" in features:
            seed = int(features["seed"])

        caps = normalize_capacities(capacities)
        rng = np.random.default_rng(seed)
        raw_shares = rng.uniform(0.1, 1.0, size=len(caps)).tolist()
        return shared_clamp_and_redistribute(raw_shares, B, caps)


class MaxComplexityGreedyStrategy:
    """Greedily saturates the highest complexity score (CS) carrier first, then the next."""

    @property
    def strategy_name(self) -> str:
        return "max_complexity_greedy"

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        if (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) or "triad_profile" in kwargs:
            payload_len = int(args[0]) if args else int(kwargs["payload_len"])
            triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
            caps = [
                max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            ]
            cs = [
                triad_profile.image.complexity_score,
                triad_profile.audio.complexity_score,
                triad_profile.video.complexity_score,
            ]
            order = sorted(range(3), key=lambda i: (cs[i], caps[i]), reverse=True)
            raw = [0.0] * 3
            rem = payload_len
            for idx in order:
                take = min(rem, caps[idx])
                raw[idx] = float(take)
                rem -= take

            b_list = shared_clamp_and_redistribute(raw, payload_len, caps)
            weights = {CARRIER_ORDER[i]: cs[i] for i in range(3)}
            return build_plan_from_bytes(self.strategy_name, b_list, payload_len, triad_profile, weights)

        B = int(args[0]) if args else int(kwargs.get("B", 0))
        capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
        features = args[2] if len(args) > 2 else kwargs.get("features", None)

        caps = normalize_capacities(capacities)
        cs = normalize_complexity_scores(features)

        order = sorted(range(len(caps)), key=lambda i: (cs[i], caps[i]), reverse=True)
        raw = [0.0] * len(caps)
        rem = B
        for idx in order:
            take = min(rem, caps[idx])
            raw[idx] = float(take)
            rem -= take

        return shared_clamp_and_redistribute(raw, B, caps)


class MinimaxRiskStrategy:
    """Minimizes the maximum per-carrier risk: min_b max_i (sigma_i^2 * b_i^2).

    Uses the same covariance matrix Sigma as Markowitz, optimizing:
        minimize t
        subject to:
            sigma_ii * (x_i)^2 <= t   for each carrier i
            sum(x_i) == 1
            0 <= x_i <= C_i / B
    """

    def __init__(self, covariance_matrix: Optional[np.ndarray] = None) -> None:
        self.custom_covariance = covariance_matrix

    @property
    def strategy_name(self) -> str:
        return "minimax_risk"

    def allocate(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        if (len(args) >= 2 and isinstance(args[1], MultimodalTriadProfile)) or "triad_profile" in kwargs:
            payload_len = int(args[0]) if args else int(kwargs["payload_len"])
            triad_profile: MultimodalTriadProfile = args[1] if len(args) > 1 else kwargs["triad_profile"]
            from app.allocation.risk_portfolio import (
                build_default_diagonal_covariance,
                validate_and_regularize_covariance,
            )
            caps = [
                max(0, triad_profile.image.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.audio.max_usable_payload_bytes - ASTG_HEADER_SIZE),
                max(0, triad_profile.video.max_usable_payload_bytes - ASTG_HEADER_SIZE),
            ]
            cov = self.custom_covariance if self.custom_covariance is not None else build_default_diagonal_covariance(triad_profile)
            val = validate_and_regularize_covariance(cov)
            sigma = val.matrix

            b_list = self._solve_minimax(payload_len, caps, sigma)
            weights = {CARRIER_ORDER[i]: (b_list[i] / payload_len) if payload_len > 0 else 0.0 for i in range(3)}
            return build_plan_from_bytes(self.strategy_name, b_list, payload_len, triad_profile, weights)

        B = int(args[0]) if args else int(kwargs.get("B", 0))
        capacities = args[1] if len(args) > 1 else kwargs.get("capacities", [0, 0, 0])
        features = args[2] if len(args) > 2 else kwargs.get("features", None)

        caps = normalize_capacities(capacities)
        sigma = self._extract_sigma(features)
        return self._solve_minimax(B, caps, sigma)

        caps = normalize_capacities(capacities)
        sigma = self._extract_sigma(features)
        return self._solve_minimax(B, caps, sigma)

    def _extract_sigma(self, features: Any) -> np.ndarray:
        if self.custom_covariance is not None:
            return self.custom_covariance
        if isinstance(features, dict) and "covariance_matrix" in features:
            cov = np.asarray(features["covariance_matrix"], dtype=np.float64)
            if cov.shape == (3, 3):
                return cov
        # Build diagonal from complexity scores
        cs = normalize_complexity_scores(features)
        variances = [1.0 / (c ** 2) for c in cs]
        return np.diag(variances)

    def _solve_minimax(self, B: int, caps: List[int], sigma: np.ndarray) -> List[int]:
        if B < 0:
            raise AllocationError(f"Payload length B cannot be negative: {B}")
        total_cap = sum(caps)
        if B > total_cap:
            raise MultimodalCapacityExceededError(
                f"Payload of {B} bytes exceeds combined net capacity {total_cap} bytes."
            )
        if B == 0:
            return [0] * len(caps)

        # Diagonals of sigma (per-carrier variance proxy)
        sig_diag = np.array([max(1e-6, float(sigma[i, i])) for i in range(3)], dtype=np.float64)

        # Unconstrained minimax: x_i proportional to 1 / sqrt(sig_diag[i]) = CS_i
        w_analytic = 1.0 / np.sqrt(sig_diag)
        w_analytic = w_analytic / np.sum(w_analytic)

        # Optimization variables: z = [x_0, x_1, x_2, t] where t is upper bound on sig_diag[i]*x_i^2
        B_float = float(B)
        bounds = [(0.0, min(1.0, float(caps[i]) / B_float)) for i in range(3)] + [(0.0, None)]

        def obj(z: np.ndarray) -> float:
            return float(z[3])

        def obj_grad(z: np.ndarray) -> np.ndarray:
            return np.array([0.0, 0.0, 0.0, 1.0])

        eq_cons = {
            "type": "eq",
            "fun": lambda z: np.sum(z[:3]) - 1.0,
            "jac": lambda z: np.array([1.0, 1.0, 1.0, 0.0]),
        }
        ineq_cons = [
            {
                "type": "ineq",
                "fun": lambda z, i=i: z[3] - sig_diag[i] * (z[i] ** 2),
                "jac": lambda z, i=i: np.array([
                    -2.0 * sig_diag[i] * z[i] if k == i else (1.0 if k == 3 else 0.0)
                    for k in range(4)
                ]),
            }
            for i in range(3)
        ]

        # Initial point
        x0 = np.clip(w_analytic, [b[0] for b in bounds[:3]], [b[1] for b in bounds[:3]])
        if np.sum(x0) > 0:
            x0 = x0 / np.sum(x0)
        else:
            x0 = np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0])
        t0 = float(np.max(sig_diag * (x0 ** 2)))
        z0 = np.array([x0[0], x0[1], x0[2], t0])

        res = minimize(
            obj,
            z0,
            jac=obj_grad,
            method="SLSQP",
            bounds=bounds,
            constraints=[eq_cons] + ineq_cons,
            options={"ftol": 1e-9, "maxiter": 100, "disp": False},
        )

        if res.success:
            x_opt = np.clip(res.x[:3], [b[0] for b in bounds[:3]], [b[1] for b in bounds[:3]])
            if np.sum(x_opt) > 0:
                x_opt = x_opt / np.sum(x_opt)
            b_cont = x_opt * B_float
        else:
            b_cont = x0 * B_float

        return shared_clamp_and_redistribute(b_cont.tolist(), B, caps)
