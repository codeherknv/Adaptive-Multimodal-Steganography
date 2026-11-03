"""Comprehensive unit and mathematical tests for Risk-Portfolio (Markowitz) allocation strategy."""

import math
from typing import Dict
import numpy as np
import pytest

from app.allocation.allocator import (
    FixedBaselineStrategy,
    AdaptiveFeatureStrategy,
    get_allocation_strategy,
    MultimodalCapacityExceededError,
    AllocationError,
)
from app.allocation.profiler import (
    ImageProfile,
    AudioProfile,
    VideoProfile,
    MultimodalTriadProfile,
)
from app.allocation.risk_portfolio import (
    CARRIER_ORDER,
    CovarianceValidationResult,
    EfficientFrontierPoint,
    RiskPortfolioStrategy,
    build_default_diagonal_covariance,
    compute_efficient_frontier,
    compute_feasible_variance_bounds,
    discretize_allocation,
    find_feasible_polytope_vertices,
    solve_portfolio_continuous,
    validate_and_regularize_covariance,
)
from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE


def make_test_triad(
    img_cap: int = 1500,
    aud_cap: int = 2000,
    vid_cap: int = 5000,
    img_complexity: float = 0.8,
    aud_complexity: float = 0.3,
    vid_complexity: float = 0.9,
) -> MultimodalTriadProfile:
    """Helper generating reproducible MultimodalTriadProfile fixtures."""
    img = ImageProfile(
        carrier_type="image",
        width=100, height=100, channels=3, color_mode="RGB",
        total_carrier_bytes=img_cap + 14,
        header_overhead_bytes=14,
        max_usable_payload_bytes=img_cap,
        laplacian_variance=250.0,
        mean_intensity=128.0,
        std_intensity=40.0,
        edge_density=0.15,
        complexity_score=img_complexity,
    )
    aud = AudioProfile(
        carrier_type="audio",
        sample_rate=16000, bits_per_sample=16, num_channels=1, channel_layout="Mono",
        total_samples=(aud_cap + 14) * 8, duration_seconds=1.0,
        total_carrier_bytes=aud_cap + 14,
        header_overhead_bytes=14,
        max_usable_payload_bytes=aud_cap,
        rms_energy=0.25,
        sample_diff_variance=0.001,
        mean_abs_diff=0.015,
        complexity_score=aud_complexity,
    )
    vid = VideoProfile(
        carrier_type="video",
        width=64, height=64, num_frames=30, fps=25.0, duration_seconds=1.2,
        recommended_codec="FFV1", container_format="AVI",
        total_carrier_bytes=vid_cap + 14,
        header_overhead_bytes=14,
        max_usable_payload_bytes=vid_cap,
        frame_diff_variance=45.0,
        keyframe_laplacian_variance=200.0,
        complexity_score=vid_complexity,
    )
    total_cap = img_cap + aud_cap + vid_cap
    return MultimodalTriadProfile(
        image=img,
        audio=aud,
        video=vid,
        total_usable_capacity_bytes=total_cap,
        capacity_shares={
            "image": round(img_cap / total_cap, 4),
            "audio": round(aud_cap / total_cap, 4),
            "video": round(vid_cap / total_cap, 4),
        }
    )


# =====================================================================
# 1. Covariance Matrix Validation & Spectral Regularization Tests
# =====================================================================

class TestCovarianceValidation:
    def test_strictly_positive_definite_symmetric_matrix(self):
        """A valid symmetric PD matrix requires no regularization."""
        mat = np.array([
            [2.0, 0.2, 0.1],
            [0.2, 3.0, 0.3],
            [0.1, 0.3, 1.5],
        ])
        res = validate_and_regularize_covariance(mat, epsilon=1e-6)
        assert not res.was_regularized
        assert res.original_min_eigenvalue > 1.0
        assert np.allclose(res.matrix, mat, atol=1e-8)
        # Check eigenvalues
        eigvals = np.linalg.eigvalsh(res.matrix)
        assert np.all(eigvals >= 1e-6)

    def test_asymmetric_matrix_symmetrization(self):
        """An asymmetric matrix must be symmetrized and recorded."""
        mat = np.array([
            [2.0, 0.5, 0.1],
            [0.1, 3.0, 0.3],
            [0.1, 0.3, 1.5],
        ])
        res = validate_and_regularize_covariance(mat, epsilon=1e-6)
        assert res.was_regularized
        assert "asymmetric" in res.notes.lower()
        # Verify symmetry of output
        assert np.allclose(res.matrix, res.matrix.T, atol=1e-10)

    def test_indefinite_matrix_eigenvalue_flooring(self):
        """An indefinite matrix with negative eigenvalues must be spectrally floored."""
        # Matrix with eigenvalues [3, 1, -2]
        Q, _ = np.linalg.qr(np.random.default_rng(42).standard_normal((3, 3)))
        eigvals = np.array([3.0, 1.0, -2.0])
        mat = Q @ np.diag(eigvals) @ Q.T

        res = validate_and_regularize_covariance(mat, epsilon=1e-6)
        assert res.was_regularized
        assert res.original_min_eigenvalue < 0.0
        assert "floored" in res.notes.lower()

        # Regularized matrix must have all eigenvalues >= epsilon
        new_eigvals = np.linalg.eigvalsh(res.matrix)
        assert np.all(new_eigvals >= 1e-6 - 1e-12)
        assert np.isclose(new_eigvals[0], 1e-6, atol=1e-8)
        assert np.allclose(res.matrix, res.matrix.T, atol=1e-10)

    def test_invalid_shape_raises_value_error(self):
        with pytest.raises(ValueError, match=r"shape \(3, 3\)"):
            validate_and_regularize_covariance(np.eye(4))

    def test_default_diagonal_covariance_properties(self):
        triad = make_test_triad(img_complexity=0.8, aud_complexity=0.3, vid_complexity=0.9)
        sigma = build_default_diagonal_covariance(triad)

        assert sigma.shape == (3, 3)
        assert np.allclose(sigma, np.diag(np.diag(sigma)))
        # High complexity -> small variance
        # Image (0.8) -> 1 / 0.64 = 1.5625
        # Audio (0.3) -> 1 / 0.09 = 11.1111
        # Video (0.9) -> 1 / 0.81 = 1.2345
        assert np.isclose(sigma[0, 0], 1.0 / (0.8 ** 2))
        assert np.isclose(sigma[1, 1], 1.0 / (0.3 ** 2))
        assert np.isclose(sigma[2, 2], 1.0 / (0.9 ** 2))
        # Audio variance (penalty) must be much higher than video variance
        assert sigma[1, 1] > sigma[2, 2]


# =====================================================================
# 2. Feasible Polytope Vertices & Variance Bounds Tests
# =====================================================================

class TestFeasiblePolytopeAndBounds:
    def test_zero_payload_bounds(self):
        caps = {"image": 1000, "audio": 1000, "video": 1000}
        sigma = np.eye(3)
        v_min, v_max = compute_feasible_variance_bounds(caps, 0, sigma)
        assert v_min == 0.0
        assert v_max == 0.0

    def test_vertices_satisfy_equality_and_bounds(self):
        caps = {"image": 500, "audio": 800, "video": 1200}
        B = 1000
        vertices = find_feasible_polytope_vertices(caps, B)
        assert len(vertices) >= 1

        for v in vertices:
            assert np.isclose(np.sum(v), B, atol=1e-4)
            assert 0.0 <= v[0] <= caps["image"] + 1e-4
            assert 0.0 <= v[1] <= caps["audio"] + 1e-4
            assert 0.0 <= v[2] <= caps["video"] + 1e-4

    def test_variance_bounds_ordering(self):
        caps = {"image": 1000, "audio": 1500, "video": 2000}
        sigma = np.diag([2.0, 10.0, 1.0])
        v_min, v_max = compute_feasible_variance_bounds(caps, 800, sigma)
        assert v_min >= 0.0
        assert v_max >= v_min


# =====================================================================
# 3. Continuous Optimization & Risk-Tolerance Monotonicity Tests
# =====================================================================

class TestContinuousOptimization:
    def test_continuous_qp_satisfies_constraints(self):
        caps = {"image": 1000, "audio": 2000, "video": 3000}
        B = 1500
        sigma = np.diag([4.0, 1.0, 9.0])
        cont_b, ok, msg = solve_portfolio_continuous(caps, B, risk_tolerance=0.5, sigma=sigma)
        assert ok
        assert np.isclose(np.sum(cont_b), B, atol=1e-4)
        for i, c in enumerate(CARRIER_ORDER):
            assert 0.0 <= cont_b[i] <= caps[c] + 1e-4

    def test_risk_tolerance_tradeoff_monotonicity(self):
        """As risk_tolerance lambda increases from 0.0 to 1.0:
        - Capacity deviation D_norm(x) should monotonically decrease (or stay within solver tolerance).
        - Portfolio variance V_norm(x) should monotonically increase (or stay within solver tolerance).
        """
        caps = {"image": 1000, "audio": 2000, "video": 3000}
        total_net = sum(caps.values())
        w_cap = np.array([caps[c] / total_net for c in CARRIER_ORDER])
        B = 1200
        # Distinct variances to ensure non-degenerate trade-off
        sigma = np.diag([1.0, 16.0, 4.0])
        tr_sigma = np.trace(sigma)

        lambdas = [0.0, 0.25, 0.5, 0.75, 1.0]
        v_norms = []
        d_norms = []

        for lam in lambdas:
            b, ok, _ = solve_portfolio_continuous(caps, B, risk_tolerance=lam, sigma=sigma)
            assert ok
            x = b / B
            v_norm = float(x @ sigma @ x) / tr_sigma
            d_norm = 0.5 * float(np.sum((x - w_cap) ** 2))
            v_norms.append(v_norm)
            d_norms.append(d_norm)

        # Numerical tolerance for SLSQP interior point convergence
        tol = 1e-4

        # D_norm must not increase as lambda increases (moving closer to capacity proportionality)
        for i in range(len(d_norms) - 1):
            assert d_norms[i] >= d_norms[i + 1] - tol, (
                f"D_norm violated monotonicity at lambda={lambdas[i]}: {d_norms[i]} < {d_norms[i+1]}"
            )

        # V_norm must not decrease as lambda increases (accepting higher variance for capacity balance)
        for i in range(len(v_norms) - 1):
            assert v_norms[i] <= v_norms[i + 1] + tol, (
                f"V_norm violated monotonicity at lambda={lambdas[i]}: {v_norms[i]} > {v_norms[i+1]}"
            )


# =====================================================================
# 4. Integer Discretization & Edge Case Tests
# =====================================================================

class TestDiscretization:
    def test_zero_payload(self):
        caps = {"image": 500, "audio": 500, "video": 500}
        res = discretize_allocation(np.zeros(3), caps, 0)
        assert res == {"image": 0, "audio": 0, "video": 0}

    def test_exact_byte_conservation_prime_payload(self):
        caps = {"image": 1000, "audio": 1500, "video": 2000}
        cont_b = np.array([333.333, 499.999, 137.668])
        B = 971  # Prime number
        res = discretize_allocation(cont_b, caps, B)
        assert sum(res.values()) == B
        for c in CARRIER_ORDER:
            assert 0 <= res[c] <= caps[c]

    def test_saturated_carriers_boundary(self):
        caps = {"image": 100, "audio": 200, "video": 300}
        total = sum(caps.values())
        cont_b = np.array([100.0, 200.0, 300.0])
        res = discretize_allocation(cont_b, caps, total)
        assert res == caps
        assert sum(res.values()) == total

    def test_carrier_with_zero_capacity(self):
        caps = {"image": 500, "audio": 0, "video": 800}
        cont_b = np.array([250.0, 0.0, 250.0])
        res = discretize_allocation(cont_b, caps, 500)
        assert res["audio"] == 0
        assert sum(res.values()) == 500
        assert res["image"] <= caps["image"]
        assert res["video"] <= caps["video"]

    def test_deterministic_tie_breaking(self):
        caps = {"image": 100, "audio": 100, "video": 100}
        # Identical fractions: 33.333 each for B=100
        cont_b = np.array([100.0 / 3.0, 100.0 / 3.0, 100.0 / 3.0])
        res1 = discretize_allocation(cont_b, caps, 100)
        res2 = discretize_allocation(cont_b, caps, 100)
        assert res1 == res2
        assert sum(res1.values()) == 100
        # By deterministic index ordering (Image first):
        # 33 + 33 + 33 = 99, 1 remainder byte goes to Image
        assert res1["image"] == 34
        assert res1["audio"] == 33
        assert res1["video"] == 33


# =====================================================================
# 5. RiskPortfolioStrategy Integration & Factory Tests
# =====================================================================

class TestRiskPortfolioStrategy:
    def test_factory_registration(self):
        for name in ("portfolio", "risk_portfolio", "markowitz", "PORTFOLIO"):
            strat = get_allocation_strategy(name)
            assert isinstance(strat, RiskPortfolioStrategy)
            assert strat.strategy_name == "portfolio"

    def test_valid_allocation_plan_structure(self):
        triad = make_test_triad(img_cap=1200, aud_cap=1500, vid_cap=3000)
        strat = RiskPortfolioStrategy(risk_tolerance=0.5)
        payload_len = 800
        plan = strat.allocate(payload_len, triad)

        assert plan.strategy_name == "portfolio"
        assert plan.total_payload_bytes == payload_len
        assert sum(a.payload_bytes for a in plan.allocations.values()) == payload_len

        # Check contiguous non-overlapping slices
        curr = 0
        for c in CARRIER_ORDER:
            start, end = plan.slice_offsets[c]
            assert start == curr
            assert end - start == plan.allocations[c].payload_bytes
            curr = end
        assert curr == payload_len

        # Check internal telemetry stored on strategy instance
        assert strat.last_validation_result is not None
        assert not strat.last_validation_result.was_regularized
        assert 0.0 <= strat.last_relative_risk <= 1.0

        # Check portfolio_metadata in plan
        assert plan.portfolio_metadata is not None
        assert "relative_risk" in plan.portfolio_metadata
        assert "covariance_matrix" in plan.portfolio_metadata
        assert "efficient_frontier" in plan.portfolio_metadata
        assert "comparison_points" in plan.portfolio_metadata
        assert "fixed" in plan.portfolio_metadata["comparison_points"]
        assert "adaptive" in plan.portfolio_metadata["comparison_points"]

    def test_custom_asymmetric_covariance_handled_safely(self):
        triad = make_test_triad(img_cap=1000, aud_cap=1000, vid_cap=1000)
        # Supply asymmetric custom covariance
        cov = np.array([
            [2.0, 0.9, 0.1],
            [0.1, 3.0, 0.4],
            [0.1, 0.2, 1.5],
        ])
        strat = RiskPortfolioStrategy(risk_tolerance=0.5, covariance_matrix=cov)
        plan = strat.allocate(300, triad)

        assert strat.last_validation_result.was_regularized
        assert sum(a.payload_bytes for a in plan.allocations.values()) == 300

    def test_insufficient_capacity_raises_error(self):
        triad = make_test_triad(img_cap=100, aud_cap=100, vid_cap=100)
        # Net capacity is 3 * (100 - 34) = 198
        strat = RiskPortfolioStrategy()
        with pytest.raises(MultimodalCapacityExceededError):
            strat.allocate(500, triad)

    def test_weights_config_lambda_override(self):
        triad = make_test_triad()
        strat = RiskPortfolioStrategy(risk_tolerance=0.2)
        plan = strat.allocate(500, triad, weights_config={"risk_tolerance": 0.9})
        # Verify the allocation executed with lambda=0.9
        for alloc in plan.allocations.values():
            assert "lambda=0.90" in alloc.reason


# =====================================================================
# 6. Efficient Frontier Tests
# =====================================================================

class TestEfficientFrontier:
    def test_frontier_calculation(self):
        triad = make_test_triad(img_cap=1000, aud_cap=1000, vid_cap=1000)
        pts = compute_efficient_frontier(triad, num_points=10)

        assert len(pts) >= 2
        # First point is 0 payload with 0 variance
        assert pts[0].payload_bytes == 0
        assert pts[0].unnormalized_variance == 0.0

        # Last point is total net capacity
        net_total = sum(
            max(0, cap - ASTG_HEADER_SIZE)
            for cap in [triad.image.max_usable_payload_bytes, triad.audio.max_usable_payload_bytes, triad.video.max_usable_payload_bytes]
        )
        assert pts[-1].payload_bytes == net_total

        # Check monotonically increasing payload steps
        for i in range(len(pts) - 1):
            assert pts[i].payload_bytes < pts[i + 1].payload_bytes
            assert pts[i].unnormalized_variance <= pts[i + 1].unnormalized_variance + 1e-4

        # Verify serialization
        d = pts[0].to_dict()
        assert "payload_bytes" in d
        assert "unnormalized_variance" in d
        assert "allocations" in d


# =====================================================================
# 7. Comparison with Fixed and Adaptive on Identical Triad
# =====================================================================

class TestComparisonWithExistingStrategies:
    def test_all_strategies_exact_conservation_on_identical_inputs(self):
        triad = make_test_triad(
            img_cap=1000, aud_cap=1500, vid_cap=4000,
            img_complexity=0.85, aud_complexity=0.25, vid_complexity=0.95
        )
        payload = 900

        fixed = FixedBaselineStrategy()
        adaptive = AdaptiveFeatureStrategy()
        portfolio = RiskPortfolioStrategy(risk_tolerance=0.0)  # Pure minimal variance

        plan_fixed = fixed.allocate(payload, triad)
        plan_adaptive = adaptive.allocate(payload, triad)
        plan_portfolio = portfolio.allocate(payload, triad)

        # All 3 conserve exact bytes
        assert sum(a.payload_bytes for a in plan_fixed.allocations.values()) == payload
        assert sum(a.payload_bytes for a in plan_adaptive.allocations.values()) == payload
        assert sum(a.payload_bytes for a in plan_portfolio.allocations.values()) == payload

        # Fixed splits 300 to each
        assert plan_fixed.allocations["image"].payload_bytes == 300
        assert plan_fixed.allocations["audio"].payload_bytes == 300
        assert plan_fixed.allocations["video"].payload_bytes == 300

        # Audio has very low complexity (0.25), so Portfolio at lambda=0 penalizes audio heavily
        # Audio variance sigma_A^2 = 1 / 0.0625 = 16.0 vs Video sigma_V^2 = 1 / 0.9025 ~ 1.1
        # Therefore portfolio puts far fewer bytes into audio than fixed
        assert plan_portfolio.allocations["audio"].payload_bytes < plan_fixed.allocations["audio"].payload_bytes
