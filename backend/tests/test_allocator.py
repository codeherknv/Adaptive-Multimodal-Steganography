"""Tests for multimodal payload allocation strategies (Phase 6)."""

import pytest

from app.allocation.profiler import (
    ImageProfile,
    AudioProfile,
    VideoProfile,
    MultimodalTriadProfile,
)
from app.allocation.allocator import (
    CarrierAllocation,
    AllocationPlan,
    FixedBaselineStrategy,
    AdaptiveFeatureStrategy,
    get_allocation_strategy,
    MultimodalCapacityExceededError,
    InvalidStrategyError,
)
from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE


def make_mock_triad_profile(
    img_cap: int = 1500,
    aud_cap: int = 2000,
    vid_cap: int = 5000,
    img_complexity: float = 0.8,
    aud_complexity: float = 0.4,
    vid_complexity: float = 0.9,
) -> MultimodalTriadProfile:
    """Helper creating a deterministic mock MultimodalTriadProfile."""
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


class TestFixedBaselineStrategy:
    def test_equal_split_with_ample_capacity(self):
        triad = make_mock_triad_profile(img_cap=1000, aud_cap=1000, vid_cap=1000)
        strategy = FixedBaselineStrategy()
        payload_len = 300
        plan = strategy.allocate(payload_len, triad)

        assert isinstance(plan, AllocationPlan)
        assert plan.strategy_name == "fixed"
        assert plan.total_payload_bytes == 300
        assert sum(a.payload_bytes for a in plan.allocations.values()) == 300

        # Each carrier should receive exactly 100 bytes
        assert plan.allocations["image"].payload_bytes == 100
        assert plan.allocations["audio"].payload_bytes == 100
        assert plan.allocations["video"].payload_bytes == 100

        # Check contiguous slice offsets
        assert plan.slice_offsets["image"] == (0, 100)
        assert plan.slice_offsets["audio"] == (100, 200)
        assert plan.slice_offsets["video"] == (200, 300)

        # Check that overhead accounted for ASTG headers
        assert plan.allocations["image"].chunk_overhead_bytes == ASTG_HEADER_SIZE
        assert plan.allocations["image"].total_carrier_payload_bytes == 100 + ASTG_HEADER_SIZE

    def test_saturated_carrier_clamping_and_waterfilling(self):
        # Image can only take 50 bytes net (84 usable - 34 overhead = 50)
        triad = make_mock_triad_profile(img_cap=84, aud_cap=2000, vid_cap=2000)
        strategy = FixedBaselineStrategy()
        payload_len = 300
        plan = strategy.allocate(payload_len, triad)

        assert sum(a.payload_bytes for a in plan.allocations.values()) == 300
        # Image must be clamped to exactly its net capacity 50
        assert plan.allocations["image"].payload_bytes == 50
        assert "clamped" in plan.allocations["image"].reason.lower()

        # Remaining 250 bytes distributed between audio and video (125 each)
        assert plan.allocations["audio"].payload_bytes == 125
        assert plan.allocations["video"].payload_bytes == 125

    def test_payload_exceeding_total_net_capacity_rejected(self):
        triad = make_mock_triad_profile(img_cap=100, aud_cap=100, vid_cap=100)
        # Net capacities are: 100-34 = 66 each, total net = 198 bytes
        strategy = FixedBaselineStrategy()
        with pytest.raises(MultimodalCapacityExceededError):
            strategy.allocate(250, triad)

    def test_zero_payload(self):
        triad = make_mock_triad_profile()
        strategy = FixedBaselineStrategy()
        plan = strategy.allocate(0, triad)
        assert plan.total_payload_bytes == 0
        assert sum(a.payload_bytes for a in plan.allocations.values()) == 0


class TestAdaptiveFeatureStrategy:
    def test_adaptive_biasing_toward_complex_carrier(self):
        # Image has high complexity (0.9), Audio has low complexity (0.1), Video medium (0.5)
        # All have equal usable capacity (1000)
        triad = make_mock_triad_profile(
            img_cap=1000, aud_cap=1000, vid_cap=1000,
            img_complexity=0.9, aud_complexity=0.1, vid_complexity=0.5
        )
        strategy = AdaptiveFeatureStrategy()
        payload_len = 300
        plan = strategy.allocate(payload_len, triad)

        assert sum(a.payload_bytes for a in plan.allocations.values()) == 300
        # High complexity image should receive significantly more bytes than low complexity audio
        assert plan.allocations["image"].payload_bytes > plan.allocations["audio"].payload_bytes
        assert plan.allocations["video"].payload_bytes > plan.allocations["audio"].payload_bytes
        assert "proportional" in plan.allocations["image"].reason.lower()

    def test_adaptive_determinism(self):
        triad = make_mock_triad_profile()
        strategy = AdaptiveFeatureStrategy()
        plan1 = strategy.allocate(512, triad)
        plan2 = strategy.allocate(512, triad)

        assert plan1.allocations["image"].payload_bytes == plan2.allocations["image"].payload_bytes
        assert plan1.allocations["audio"].payload_bytes == plan2.allocations["audio"].payload_bytes
        assert plan1.allocations["video"].payload_bytes == plan2.allocations["video"].payload_bytes

    def test_adaptive_overcapacity_rejected(self):
        triad = make_mock_triad_profile(img_cap=50, aud_cap=50, vid_cap=50)
        strategy = AdaptiveFeatureStrategy()
        with pytest.raises(MultimodalCapacityExceededError):
            strategy.allocate(1000, triad)


class TestStrategyFactory:
    def test_factory_resolution(self):
        s_fix = get_allocation_strategy("fixed")
        assert isinstance(s_fix, FixedBaselineStrategy)
        assert s_fix.strategy_name == "fixed"

        s_adapt = get_allocation_strategy("adaptive")
        assert isinstance(s_adapt, AdaptiveFeatureStrategy)
        assert s_adapt.strategy_name == "adaptive"

    def test_factory_invalid_strategy(self):
        with pytest.raises(InvalidStrategyError):
            get_allocation_strategy("deep_reinforcement_learning")
