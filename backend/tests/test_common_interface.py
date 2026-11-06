"""Parametrized unit tests for the common allocation interface across all 8 strategies.

Verifies:
1. Exact byte conservation: sum(b_i) == B.
2. Strict capacity bounds: 0 <= b_i <= C_i.
3. Non-negativity and integer output.
4. Edge cases:
   - B near total capacity (C_total - 1, C_total)
   - One or more carriers with zero capacity (C_i == 0)
   - B > total capacity fails cleanly (raises MultimodalCapacityExceededError)
   - B == 0 returns [0, 0, 0]
   - Negative B raises AllocationError
5. Mathematical convergence: Markowitz at lambda=1.0 matches capacity-proportional
   with diagonal covariance.
6. Support for both list and dict input representations.
7. Support for full AllocationPlan generation when given a MultimodalTriadProfile.
"""

from typing import Any, Dict, List
import numpy as np
import pytest

from app.allocation.allocator import (
    AllocationError,
    AllocationPlan,
    FixedBaselineStrategy,
    AdaptiveFeatureStrategy,
    MultimodalCapacityExceededError,
    get_allocation_strategy,
)
from app.allocation.risk_portfolio import RiskPortfolioStrategy
from app.allocation.strategies import (
    CapacityProportionalStrategy,
    SquareRootLawStrategy,
    RandomKeySeededStrategy,
    MaxComplexityGreedyStrategy,
    MinimaxRiskStrategy,
)
from app.allocation.profiler import (
    AudioProfile,
    ImageProfile,
    MultimodalTriadProfile,
    VideoProfile,
)


from tests.test_allocator import make_mock_triad_profile


ALL_STRATEGIES = [
    FixedBaselineStrategy(),
    AdaptiveFeatureStrategy(),
    RiskPortfolioStrategy(risk_tolerance=0.0),
    RiskPortfolioStrategy(risk_tolerance=0.5),
    RiskPortfolioStrategy(risk_tolerance=1.0),
    CapacityProportionalStrategy(),
    SquareRootLawStrategy(),
    RandomKeySeededStrategy(seed=42),
    MaxComplexityGreedyStrategy(),
    MinimaxRiskStrategy(),
]


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: getattr(s, "strategy_name", str(s)))
class TestCommonAllocationInterface:
    """Test standard common interface allocate(B, capacities, features) across all strategies."""

    def test_byte_conservation_and_bounds(self, strategy: Any):
        capacities = [300, 500, 700]
        features = {"complexity_scores": [0.8, 0.4, 0.6]}

        for B in [1, 10, 50, 150, 450, 800, 1400]:
            alloc = strategy.allocate(B, capacities, features)
            assert isinstance(alloc, list), f"Expected list, got {type(alloc)}"
            assert len(alloc) == 3, f"Expected 3 allocations, got {len(alloc)}"
            assert all(isinstance(x, int) for x in alloc), f"Non-integer bytes: {alloc}"
            assert sum(alloc) == B, f"Byte sum mismatch: sum={sum(alloc)} != B={B} for strategy {strategy.strategy_name}"
            for i, c in enumerate(capacities):
                assert 0 <= alloc[i] <= c, f"Capacity violation: alloc[{i}]={alloc[i]} not in [0, {c}]"

    def test_edge_case_b_zero(self, strategy: Any):
        capacities = [200, 300, 400]
        alloc = strategy.allocate(0, capacities, None)
        assert alloc == [0, 0, 0]

    def test_edge_case_b_near_total_capacity(self, strategy: Any):
        capacities = [100, 200, 300]  # total = 600
        features = {"complexity_scores": [0.3, 0.9, 0.5]}

        # B = total - 1
        alloc_near = strategy.allocate(599, capacities, features)
        assert sum(alloc_near) == 599
        assert all(0 <= alloc_near[i] <= capacities[i] for i in range(3))

        # B = total exact
        alloc_exact = strategy.allocate(600, capacities, features)
        assert sum(alloc_exact) == 600
        assert alloc_exact == capacities

    def test_edge_case_zero_capacity_carrier(self, strategy: Any):
        # Audio carrier has 0 capacity
        capacities = [250, 0, 400]
        features = {"complexity_scores": [0.7, 0.1, 0.9]}
        alloc = strategy.allocate(300, capacities, features)

        assert sum(alloc) == 300
        assert alloc[1] == 0, f"Carrier with 0 capacity was allocated bytes: {alloc[1]}"
        assert alloc[0] <= 250
        assert alloc[2] <= 400

    def test_edge_case_exceeds_total_capacity_raises(self, strategy: Any):
        capacities = [100, 150, 200]  # total = 450
        with pytest.raises(MultimodalCapacityExceededError):
            strategy.allocate(451, capacities, None)

    def test_negative_payload_raises(self, strategy: Any):
        capacities = [100, 100, 100]
        with pytest.raises(AllocationError):
            strategy.allocate(-5, capacities, None)

    def test_dict_capacities_input_support(self, strategy: Any):
        cap_dict = {"image": 150, "audio": 250, "video": 350}
        features = {"image": 0.5, "audio": 0.5, "video": 0.5}
        alloc = strategy.allocate(200, cap_dict, features)

        assert sum(alloc) == 200
        assert 0 <= alloc[0] <= 150
        assert 0 <= alloc[1] <= 250
        assert 0 <= alloc[2] <= 350

    def test_full_allocation_plan_interface(self, strategy: Any):
        triad = make_mock_triad_profile(img_cap=500, aud_cap=500, vid_cap=500, img_complexity=0.8, aud_complexity=0.3, vid_complexity=0.6)
        plan = strategy.allocate(300, triad)

        assert isinstance(plan, AllocationPlan)
        assert plan.total_payload_bytes == 300
        assigned_sum = sum(a.payload_bytes for a in plan.allocations.values())
        assert assigned_sum == 300
        for c_type in ["image", "audio", "video"]:
            alloc_c = plan.allocations[c_type]
            assert 0 <= alloc_c.payload_bytes <= alloc_c.carrier_net_capacity_bytes


class TestSpecificStrategyBehaviors:
    """Tests testing specific mathematical properties of individual strategies."""

    def test_markowitz_lambda_1_matches_capacity_proportional(self):
        """Markowitz at lambda=1.0 minimizes deviation from capacity shares, matching CapacityProportional."""
        markowitz = RiskPortfolioStrategy(risk_tolerance=1.0)
        cap_prop = CapacityProportionalStrategy()

        test_cases = [
            ([200, 400, 600], 300),
            ([100, 500, 50], 250),
            ([300, 300, 300], 450),
            ([1000, 500, 2000], 1200),
            ([123, 456, 789], 555),
        ]

        for caps, B in test_cases:
            alloc_m = markowitz.allocate(B, caps, None)
            alloc_cp = cap_prop.allocate(B, caps, None)
            assert alloc_m == alloc_cp, (
                f"Mismatch for caps={caps}, B={B}:\n"
                f"Markowitz(lambda=1.0): {alloc_m}\n"
                f"CapacityProportional:  {alloc_cp}"
            )

    def test_max_complexity_greedy_order(self):
        greedy = MaxComplexityGreedyStrategy()
        # Audio has highest CS (0.95), then Video (0.70), Image (0.20)
        features = {"complexity_scores": [0.20, 0.95, 0.70]}
        caps = [100, 100, 100]

        # Payload 80 should go entirely to audio
        alloc1 = greedy.allocate(80, caps, features)
        assert alloc1 == [0, 80, 0]

        # Payload 150 should saturate audio (100) and put 50 into video
        alloc2 = greedy.allocate(150, caps, features)
        assert alloc2 == [0, 100, 50]

        # Payload 250 should saturate audio (100), video (100), and put 50 into image
        alloc3 = greedy.allocate(250, caps, features)
        assert alloc3 == [50, 100, 100]

    def test_square_root_law_compressive_scaling(self):
        sqrt_strat = SquareRootLawStrategy()
        # Capacity ratio is 1:4:16
        caps = [100, 400, 1600]
        # sqrt(C) ratio is 10:20:40 = 1:2:4
        alloc = sqrt_strat.allocate(700, caps, None)
        # Expected shares: 100, 200, 400
        assert alloc == [100, 200, 400]

    def test_random_key_seeded_reproducibility(self):
        r1 = RandomKeySeededStrategy(seed=123)
        r2 = RandomKeySeededStrategy(seed=123)
        r3 = RandomKeySeededStrategy(seed=999)
        caps = [500, 500, 500]

        alloc1 = r1.allocate(300, caps, None)
        alloc2 = r2.allocate(300, caps, None)
        alloc3 = r3.allocate(300, caps, None)

        assert alloc1 == alloc2, "Identical seeds must produce identical allocations"
        # Different seeds should produce different allocations with high probability
        assert alloc1 != alloc3, "Different seeds should produce different allocations"

    def test_minimax_risk_equalizes_unconstrained_carrier_risk(self):
        """Under equal capacities, minimax allocates inversely proportional to sigma_i."""
        minimax = MinimaxRiskStrategy()
        # Complexity scores: 0.8, 0.4, 0.2
        # sigma_i = 1/CS_i -> sigma = [1.25, 2.5, 5.0]
        # Risk R_i = (b_i * sigma_i)^2
        # Equalizing risk implies b_i * sigma_i is constant -> b_i proportional to CS_i
        features = {"complexity_scores": [0.8, 0.4, 0.2]}
        caps = [1000, 1000, 1000]
        # Total CS sum = 1.4 -> ratios: 0.8/1.4 ≈ 57.1%, 0.4/1.4 ≈ 28.6%, 0.2/1.4 ≈ 14.3%
        alloc = minimax.allocate(700, caps, features)
        assert sum(alloc) == 700
        # Check ordering: highest CS carrier gets largest allocation
        assert alloc[0] > alloc[1] > alloc[2]

    def test_factory_function_resolves_all_strategies(self):
        all_names = [
            "fixed", "adaptive", "portfolio", "risk_portfolio", "markowitz",
            "capacity_proportional", "proportional", "square_root", "sqrt",
            "square_root_law", "random", "random_key", "max_complexity", "greedy",
            "minimax", "minimax_risk"
        ]
        for name in all_names:
            strat = get_allocation_strategy(name)
            assert strat is not None
            assert hasattr(strat, "allocate")
            assert hasattr(strat, "strategy_name")
