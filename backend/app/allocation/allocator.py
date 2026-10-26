"""Multimodal payload allocation strategies across heterogeneous carriers.

This module implements deterministic payload allocation across Image, Audio, and Video carriers:
1. Fixed Baseline Strategy:
   - Strives for equal (1/3 each) payload distribution across available carriers.
   - Clamps any carrier that lacks sufficient capacity and redistributes overflow to remaining carriers.
2. Adaptive Feature-Weighted Strategy:
   - Calculates a Steganographic Suitability Weight for each carrier based on measured media features
     (Laplacian variance, acoustic RMS dynamism, video frame-difference variance) and carrier capacity.
   - Allocates more bytes to complex, high-entropy carriers with greater capacity while respecting
     strict capacity constraints.

Capacity Overhead Accounting:
----------------------------
Each allocated payload slice requires an ASTG binary packet header (34 bytes).
In turn, each carrier module wraps the serialized ASTG chunk in a 14-byte carrier framing header.
Therefore:
    Carrier Total Usable Capacity C_i (bytes) = max(0, RawCarrierBytes - 14)
    Carrier Net Envelope Payload Capacity M_i (bytes) = max(0, C_i - 34)

Total net capacity across all carriers must be >= payload_len, otherwise
MultimodalCapacityExceededError is raised immediately.

Scientific Notice:
-----------------
The adaptive strategy implements a deterministic rate-distortion heuristic. It does NOT
claim superior security or imperceptibility over the baseline without empirical steganalysis
verification. The module is engineered with an abstract base class so future ML-guided
optimization models can drop in seamlessly.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.core.payload_codec import HEADER_SIZE as ASTG_HEADER_SIZE
from app.allocation.profiler import MultimodalTriadProfile


class AllocationError(Exception):
    """Base exception for payload allocation errors."""
    pass


class MultimodalCapacityExceededError(AllocationError):
    """Raised when the payload cannot fit within the available carrier capacities."""
    pass


class InvalidStrategyError(AllocationError):
    """Raised when an unknown allocation strategy is requested."""
    pass


@dataclass(frozen=True)
class CarrierAllocation:
    """Detailed allocation outcome for a single carrier channel.

    Attributes:
        carrier_type: 'image', 'audio', or 'video'.
        payload_bytes: Number of encrypted envelope bytes assigned to this carrier.
        chunk_overhead_bytes: 34 bytes for ASTG packet header.
        total_carrier_payload_bytes: payload_bytes + chunk_overhead_bytes.
        carrier_usable_capacity_bytes: Carrier capacity before ASTG overhead.
        carrier_net_capacity_bytes: Maximum envelope bytes this carrier could take (C_i - 34).
        utilization_ratio: total_carrier_payload_bytes / carrier_usable_capacity_bytes.
        complexity_score: Profiling complexity score in [0.05, 1.0].
        weight: Computed allocation suitability weight.
        reason: Human-readable explanation of why this byte count was chosen.
    """
    carrier_type: str
    payload_bytes: int
    chunk_overhead_bytes: int
    total_carrier_payload_bytes: int
    carrier_usable_capacity_bytes: int
    carrier_net_capacity_bytes: int
    utilization_ratio: float
    complexity_score: float
    weight: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AllocationPlan:
    """Complete allocation plan for the multimodal triad.

    Attributes:
        strategy_name: 'fixed' or 'adaptive'.
        total_payload_bytes: Total length of the encrypted envelope to distribute.
        total_usable_capacity_bytes: Total usable capacity across all 3 carriers.
        total_net_capacity_bytes: Usable capacity minus 3 * 34 bytes chunk overhead.
        overall_utilization_ratio: Total bytes embedded / total capacity.
        allocations: Dictionary mapping carrier_type to CarrierAllocation.
        slice_offsets: Dictionary mapping carrier_type to (start_idx, end_idx) byte range.
    """
    strategy_name: str
    total_payload_bytes: int
    total_usable_capacity_bytes: int
    total_net_capacity_bytes: int
    overall_utilization_ratio: float
    allocations: Dict[str, CarrierAllocation]
    slice_offsets: Dict[str, Tuple[int, int]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_payload_bytes": self.total_payload_bytes,
            "total_usable_capacity_bytes": self.total_usable_capacity_bytes,
            "total_net_capacity_bytes": self.total_net_capacity_bytes,
            "overall_utilization_ratio": self.overall_utilization_ratio,
            "allocations": {k: v.to_dict() for k, v in self.allocations.items()},
            "slice_offsets": {k: list(v) for k, v in self.slice_offsets.items()},
        }


class BaseAllocationStrategy(ABC):
    """Abstract base class for multimodal allocation strategies."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Unique identifier for this strategy."""
        pass

    @abstractmethod
    def allocate(
        self,
        payload_len: int,
        triad_profile: MultimodalTriadProfile,
        weights_config: Optional[Dict[str, float]] = None,
    ) -> AllocationPlan:
        """Compute exact byte allocation across image, audio, and video carriers.

        Args:
            payload_len: Total bytes in the encrypted envelope.
            triad_profile: Profile containing capacities and media features.
            weights_config: Optional carrier weight tuning dictionary.

        Returns:
            Validated AllocationPlan.

        Raises:
            MultimodalCapacityExceededError: If payload cannot fit within capacities.
        """
        pass


class FixedBaselineStrategy(BaseAllocationStrategy):
    """Deterministic equal-split baseline allocation strategy.

    Algorithm:
    1. Checks if total net capacity >= payload_len.
    2. Computes equal target share: T = payload_len // 3.
    3. If any carrier's net capacity < T, clamp that carrier to its net capacity and
       redistribute the deficit to the remaining carriers with headroom.
    4. Distributes integer remainder byte-by-byte in deterministic order (image -> audio -> video).
    5. Validates invariant: sum(allocated_bytes) == payload_len.
    """

    @property
    def strategy_name(self) -> str:
        return "fixed"

    def allocate(
        self,
        payload_len: int,
        triad_profile: MultimodalTriadProfile,
        weights_config: Optional[Dict[str, float]] = None,
    ) -> AllocationPlan:
        if payload_len < 0:
            raise AllocationError(f"Payload length cannot be negative: {payload_len}")

        carrier_order = ["image", "audio", "video"]
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

        # Iterative bounded equal allocation with overflow water-filling
        allocated: Dict[str, int] = {k: 0 for k in carrier_order}
        unallocated = payload_len
        active_carriers = set(carrier_order)

        while unallocated > 0 and active_carriers:
            share = unallocated // len(active_carriers)
            remainder = unallocated % len(active_carriers)
            clamped_this_round = False

            for c in list(active_carriers):
                # Target for this round
                tentative = allocated[c] + share
                if tentative >= net_caps[c]:
                    # Carrier saturated: clamp to its net capacity
                    unallocated -= (net_caps[c] - allocated[c])
                    allocated[c] = net_caps[c]
                    active_carriers.remove(c)
                    clamped_this_round = True

            if not clamped_this_round:
                # All active carriers can accept their share
                for c in active_carriers:
                    allocated[c] += share
                unallocated = remainder
                break

        # Distribute remaining bytes deterministically
        if unallocated > 0:
            for c in carrier_order:
                if unallocated == 0:
                    break
                headroom = net_caps[c] - allocated[c]
                take = min(unallocated, headroom)
                allocated[c] += take
                unallocated -= take

        if sum(allocated.values()) != payload_len:
            raise AllocationError(
                f"Internal error: fixed allocation sum {sum(allocated.values())} != payload {payload_len}"
            )

        # Build detailed allocation report
        allocations: Dict[str, CarrierAllocation] = {}
        slice_offsets: Dict[str, Tuple[int, int]] = {}
        curr_offset = 0

        scores = {
            "image": triad_profile.image.complexity_score,
            "audio": triad_profile.audio.complexity_score,
            "video": triad_profile.video.complexity_score,
        }

        for c in carrier_order:
            bytes_assigned = allocated[c]
            overhead = ASTG_HEADER_SIZE if bytes_assigned > 0 else 0
            total_carrier_bytes = bytes_assigned + overhead
            usable_cap = usable_caps[c]
            net_cap = net_caps[c]
            util = round(total_carrier_bytes / usable_cap, 4) if usable_cap > 0 else 0.0

            slice_offsets[c] = (curr_offset, curr_offset + bytes_assigned)
            curr_offset += bytes_assigned

            if bytes_assigned == net_cap and net_cap < (payload_len // 3):
                reason = f"Fixed baseline clamped to carrier net capacity limit ({net_cap} bytes)."
            else:
                reason = f"Fixed baseline balanced share ({bytes_assigned} bytes)."

            allocations[c] = CarrierAllocation(
                carrier_type=c,
                payload_bytes=bytes_assigned,
                chunk_overhead_bytes=overhead,
                total_carrier_payload_bytes=total_carrier_bytes,
                carrier_usable_capacity_bytes=usable_cap,
                carrier_net_capacity_bytes=net_cap,
                utilization_ratio=util,
                complexity_score=scores[c],
                weight=1.0,
                reason=reason,
            )

        overall_util = round(
            sum(a.total_carrier_payload_bytes for a in allocations.values()) / total_usable_cap, 4
        ) if total_usable_cap > 0 else 0.0

        return AllocationPlan(
            strategy_name=self.strategy_name,
            total_payload_bytes=payload_len,
            total_usable_capacity_bytes=total_usable_cap,
            total_net_capacity_bytes=total_net_cap,
            overall_utilization_ratio=overall_util,
            allocations=allocations,
            slice_offsets=slice_offsets,
        )


class AdaptiveFeatureStrategy(BaseAllocationStrategy):
    """Deterministic feature-weighted adaptive allocation strategy.

    Algorithm:
    1. Evaluates Steganographic Suitability Weight for each carrier:
       W_i = alpha_i * complexity_score_i * log2(1 + net_capacity_i)
       where:
         - alpha_i: Optional user weight modifier (default 1.0).
         - complexity_score_i: Measured media entropy / variance in [0.05, 1.0].
         - log2(1 + net_capacity_i): Diminishing-returns capacity scaling factor.
    2. Computes initial proportional target shares:
       target_i = floor( (W_i / sum(W)) * payload_len )
    3. Clamps any carrier exceeding net capacity and iteratively redistributes surplus
       to remaining unconstrained carriers proportional to their weights.
    4. Distributes integer rounding remainder to carriers with highest residual headroom.
    5. Validates invariant: sum(allocated_bytes) == payload_len.
    """

    @property
    def strategy_name(self) -> str:
        return "adaptive"

    def allocate(
        self,
        payload_len: int,
        triad_profile: MultimodalTriadProfile,
        weights_config: Optional[Dict[str, float]] = None,
    ) -> AllocationPlan:
        if payload_len < 0:
            raise AllocationError(f"Payload length cannot be negative: {payload_len}")

        carrier_order = ["image", "audio", "video"]
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

        # Baseline user weights (defaults to 1.0)
        cfg = weights_config or {}
        alphas = {
            c: max(0.1, float(cfg.get(c, 1.0))) for c in carrier_order
        }

        complexity_scores = {
            "image": triad_profile.image.complexity_score,
            "audio": triad_profile.audio.complexity_score,
            "video": triad_profile.video.complexity_score,
        }

        # 1. Compute suitability weights W_i
        weights: Dict[str, float] = {}
        for c in carrier_order:
            if net_caps[c] <= 0:
                weights[c] = 0.0
            else:
                cap_factor = math.log2(1.0 + net_caps[c])
                weights[c] = alphas[c] * complexity_scores[c] * cap_factor

        sum_weights = sum(weights.values())
        if sum_weights <= 0.0:
            # Fallback to fixed strategy if all weights are zero
            fixed_fallback = FixedBaselineStrategy()
            return fixed_fallback.allocate(payload_len, triad_profile, weights_config)

        # 2. Iterative bounded allocation
        allocated: Dict[str, int] = {k: 0 for k in carrier_order}
        active_carriers = set(c for c in carrier_order if net_caps[c] > 0)
        unallocated = payload_len

        while unallocated > 0 and active_carriers:
            curr_sum_w = sum(weights[c] for c in active_carriers)
            if curr_sum_w <= 0.0:
                # Distribute remaining evenly across active carriers
                even_share = unallocated // len(active_carriers)
                for c in active_carriers:
                    take = min(unallocated, net_caps[c] - allocated[c])
                    allocated[c] += take
                    unallocated -= take
                break

            clamped_this_round = False
            round_allocations: Dict[str, int] = {}

            for c in active_carriers:
                prop = weights[c] / curr_sum_w
                desired_addition = int(math.floor(prop * unallocated))
                tentative = allocated[c] + desired_addition

                if tentative >= net_caps[c]:
                    # Saturated carrier: clamp to net capacity
                    unallocated -= (net_caps[c] - allocated[c])
                    allocated[c] = net_caps[c]
                    active_carriers.remove(c)
                    clamped_this_round = True
                    break
                else:
                    round_allocations[c] = desired_addition

            if not clamped_this_round:
                # No carrier clamped: commit round allocations
                for c, amt in round_allocations.items():
                    allocated[c] += amt
                    unallocated -= amt
                break

        # 3. Distribute any integer rounding remainder
        if unallocated > 0:
            # Sort active carriers by residual headroom and suitability weight descending
            eligible = sorted(
                carrier_order,
                key=lambda c: (net_caps[c] - allocated[c] > 0, weights[c], net_caps[c] - allocated[c]),
                reverse=True
            )
            for c in eligible:
                if unallocated == 0:
                    break
                headroom = net_caps[c] - allocated[c]
                take = min(unallocated, headroom)
                allocated[c] += take
                unallocated -= take

        if sum(allocated.values()) != payload_len:
            raise AllocationError(
                f"Internal error: adaptive allocation sum {sum(allocated.values())} != payload {payload_len}"
            )

        # Build detailed allocation report
        allocations: Dict[str, CarrierAllocation] = {}
        slice_offsets: Dict[str, Tuple[int, int]] = {}
        curr_offset = 0

        for c in carrier_order:
            bytes_assigned = allocated[c]
            overhead = ASTG_HEADER_SIZE if bytes_assigned > 0 else 0
            total_carrier_bytes = bytes_assigned + overhead
            usable_cap = usable_caps[c]
            net_cap = net_caps[c]
            util = round(total_carrier_bytes / usable_cap, 4) if usable_cap > 0 else 0.0

            slice_offsets[c] = (curr_offset, curr_offset + bytes_assigned)
            curr_offset += bytes_assigned

            # Construct informative scientific rationale
            pct = round((bytes_assigned / payload_len) * 100, 1) if payload_len > 0 else 0.0
            if bytes_assigned >= net_cap and net_cap > 0:
                reason = (
                    f"Assigned {bytes_assigned}B ({pct}% of payload): clamped to maximum net capacity "
                    f"limit ({net_cap}B) despite high weight W={weights[c]:.2f}."
                )
            elif bytes_assigned == 0:
                reason = f"Carrier unallocated (0B): insufficient usable capacity or zero suitability weight."
            else:
                reason = (
                    f"Assigned {bytes_assigned}B ({pct}% of payload): proportional to feature complexity "
                    f"(score={complexity_scores[c]:.2f}) and capacity weight (W={weights[c]:.2f})."
                )

            allocations[c] = CarrierAllocation(
                carrier_type=c,
                payload_bytes=bytes_assigned,
                chunk_overhead_bytes=overhead,
                total_carrier_payload_bytes=total_carrier_bytes,
                carrier_usable_capacity_bytes=usable_cap,
                carrier_net_capacity_bytes=net_cap,
                utilization_ratio=util,
                complexity_score=complexity_scores[c],
                weight=round(weights[c], 3),
                reason=reason,
            )

        overall_util = round(
            sum(a.total_carrier_payload_bytes for a in allocations.values()) / total_usable_cap, 4
        ) if total_usable_cap > 0 else 0.0

        return AllocationPlan(
            strategy_name=self.strategy_name,
            total_payload_bytes=payload_len,
            total_usable_capacity_bytes=total_usable_cap,
            total_net_capacity_bytes=total_net_cap,
            overall_utilization_ratio=overall_util,
            allocations=allocations,
            slice_offsets=slice_offsets,
        )


def get_allocation_strategy(strategy_name: Literal["fixed", "adaptive"]) -> BaseAllocationStrategy:
    """Factory function resolving strategy identifier to its implementation."""
    clean_name = strategy_name.strip().lower()
    if clean_name == "fixed":
        return FixedBaselineStrategy()
    elif clean_name == "adaptive":
        return AdaptiveFeatureStrategy()
    else:
        raise InvalidStrategyError(
            f"Unknown allocation strategy '{strategy_name}'. Supported strategies: 'fixed', 'adaptive'."
        )
