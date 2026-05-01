# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Shared statistics utilities for computing period-based incident metrics.
"""

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from markupsafe import Markup


@dataclass
class PeriodStats:
    start: str  # YYYY-MM-DD, inclusive
    end: str  # YYYY-MM-DD, exclusive
    total_incidents: int
    total_entities: int  # distinct entity names (excluding unknown/None)
    top_entities: list[tuple[str, int]]  # top 5, descending by count
    severity_counts: dict[str, float]  # {"S1": %, "S2": %, "S3": %, "S4": %} as 0-100
    service_total_count: int
    service_resolved_count: int
    service_status_counts: dict[
        str, float
    ]  # {"Detected": %, "InProgress": %, "Mitigated": %, "Resolved": %} as 0-100, service bucket only
    product_total_count: int
    product_resolved_count: int
    product_status_counts: dict[
        str, float
    ]  # {"Detected": %, "InProgress": %, "Mitigated": %, "Resolved": %} as 0-100, product bucket only
    service_detection_method_counts: dict[
        str, float
    ]  # {"Manual": %, "Automation": %} as 0-100, excludes unknown, service bucket only
    product_detection_method_counts: dict[
        str, float
    ]  # {"Manual": %, "Automation": %} as 0-100, excludes unknown, product bucket only
    service_mean_tt_dec: Optional[timedelta]
    service_mean_tt_alert: Optional[timedelta]
    service_mean_tt_resp: Optional[timedelta]
    service_mean_tt_mit: Optional[timedelta]
    service_mean_tt_res: Optional[timedelta]
    service_pvariance_tt_dec: Optional[float]  # seconds²
    service_pvariance_tt_alert: Optional[float]  # seconds²
    service_pvariance_tt_resp: Optional[float]  # seconds²
    service_pvariance_tt_mit: Optional[float]  # seconds²
    service_pvariance_tt_res: Optional[float]  # seconds²
    service_count_tt_dec: int
    service_count_tt_alert: int
    service_count_tt_resp: int
    service_count_tt_mit: int
    service_count_tt_res: int
    product_mean_tt_dec: Optional[timedelta]
    product_mean_tt_alert: Optional[timedelta]
    product_mean_tt_resp: Optional[timedelta]
    product_mean_tt_mit: Optional[timedelta]
    product_mean_tt_res: Optional[timedelta]
    product_pvariance_tt_dec: Optional[float]  # seconds²
    product_pvariance_tt_alert: Optional[float]  # seconds²
    product_pvariance_tt_resp: Optional[float]  # seconds²
    product_pvariance_tt_mit: Optional[float]  # seconds²
    product_pvariance_tt_res: Optional[float]  # seconds²
    product_count_tt_dec: int
    product_count_tt_alert: int
    product_count_tt_resp: int
    product_count_tt_mit: int
    product_count_tt_res: int
    mean_action_items: Optional[
        float
    ]  # mean per resolved incident with action_items set
    pct_reports_completed: (
        float  # % of Resolved incidents with is_completed=True, 0-100
    )


@dataclass
class PeriodComparison:
    current: PeriodStats
    prior: PeriodStats


def humanize_timedelta(td: Optional[timedelta]) -> str:
    if td is None:
        return "?"

    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days:,}d")
    if hours:
        parts.append(f"{hours:,}h")
    if minutes:
        parts.append(f"{minutes:,}m")
    if seconds or not parts:
        parts.append(f"{seconds:,}s")

    # Only take the two most significant parts
    parts = parts[:2]

    return sign + " ".join(parts)


def mean_timedelta(values: list[Optional[timedelta]]) -> Optional[timedelta]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered, timedelta()) / len(filtered)


def pvariance_timedelta(values: list[Optional[timedelta]]) -> Optional[float]:
    """Returns population variance of the given timedeltas, in seconds²."""
    filtered = [v for v in values if v is not None]
    if len(filtered) < 2:
        return None
    secs = [v.total_seconds() for v in filtered]
    return statistics.pvariance(secs)


def count_timedelta(values: list[Optional[timedelta]]) -> int:
    """Returns the count of non-None timedelta values."""
    return sum(1 for v in values if v is not None)


def format_pvar(mean_td: Optional[timedelta], pvariance: Optional[float]) -> str:
    if mean_td is None or pvariance is None:
        return "\u2014"
    mean_secs = mean_td.total_seconds()
    if mean_secs == 0:
        return "\u2014"
    return f"{pvariance / (mean_secs**2):.2f}"


def format_mtt(
    mean_td: Optional[timedelta], pvariance: Optional[float], count: int
) -> str:
    if mean_td is None:
        return "\u2014"
    mean_str = humanize_timedelta(mean_td)
    mean_secs = mean_td.total_seconds()
    count_str = f"({count} values)"
    if pvariance is None or mean_secs == 0:
        return f"{mean_str} {count_str}"
    relative_variance = pvariance / (mean_secs**2)
    return f"{mean_str} {count_str} ({relative_variance:.2f} pvar)"


def direction(prior_val, current_val) -> str:
    if prior_val is None or current_val is None:
        return "same"
    if isinstance(prior_val, timedelta):
        prior_val = prior_val.total_seconds()
        current_val = current_val.total_seconds()
    if current_val > prior_val:
        return "up"
    if current_val < prior_val:
        return "down"
    return "same"


def direction_symbol(
    prior_val,
    current_val,
    up_is_good: bool = False,
    up_label: str = "higher",
    down_label: str = "lower",
) -> Markup:
    d = direction(prior_val, current_val)
    if d == "same":
        return Markup('<span style="color: #6B7280;">same</span>')
    if d == "up":
        color = "#1B991B" if up_is_good else "#991B1B"
        return Markup(
            f'<span style="color: {color}; font-weight: bold;">&#9650; {up_label}</span>'
        )
    # down
    color = "#991B1B" if up_is_good else "#1B991B"
    return Markup(
        f'<span style="color: {color}; font-weight: bold;">&#9660; {down_label}</span>'
    )


def build_period_stats(incidents, start: str, end: str) -> PeriodStats:
    # top entities
    entity_counter: Counter = Counter()
    for incident in incidents:
        if not incident.entities:
            continue
        for entity in incident.entities.split(","):
            entity = entity.strip()
            if entity:
                entity_counter[entity] += 1
    total_entities = len(entity_counter)
    top_entities = sorted(entity_counter.items(), key=lambda x: (-x[1], x[0]))[:5]

    # severity percentages
    total = len(incidents)
    sev_raw = {"S1": 0, "S2": 0, "S3": 0, "S4": 0}
    for incident in incidents:
        if incident.severity in sev_raw:
            sev_raw[incident.severity] += 1
    severity_counts = {
        k: (v / total * 100) if total else 0.0 for k, v in sev_raw.items()
    }

    # TT means by entity_bucket
    service = [i for i in incidents if i.entity_bucket == "service"]
    product = [i for i in incidents if i.entity_bucket == "product"]

    # status percentages by bucket
    def _status_counts(bucket):
        n = len(bucket)
        raw = {"Detected": 0, "InProgress": 0, "Mitigated": 0, "Resolved": 0}
        for i in bucket:
            if i.status in raw:
                raw[i.status] += 1
        return {k: (v / n * 100) if n else 0.0 for k, v in raw.items()}

    service_status_counts = _status_counts(service)
    product_status_counts = _status_counts(product)

    # detection method percentages by bucket, excluding unknown
    def _detection_counts(bucket):
        known = [i for i in bucket if i.detection_method in ("Manual", "Automation")]
        n = len(known)
        raw = {"Manual": 0, "Automation": 0}
        for i in known:
            raw[i.detection_method] += 1
        return {k: (v / n * 100) if n else 0.0 for k, v in raw.items()}

    service_detection_method_counts = _detection_counts(service)
    product_detection_method_counts = _detection_counts(product)
    service_resolved = [i for i in service if i.status == "Resolved"]
    product_resolved = [i for i in product if i.status == "Resolved"]
    service_total_count = len(service)
    service_resolved_count = len(service_resolved)
    product_total_count = len(product)
    product_resolved_count = len(product_resolved)

    resolved_with_ais = [
        i for i in incidents if i.status == "Resolved" and i.action_items is not None
    ]
    if resolved_with_ais:
        mean_action_items: Optional[float] = sum(
            len(i.action_items) for i in resolved_with_ais
        ) / len(resolved_with_ais)
    else:
        mean_action_items = None

    resolved_incidents = [i for i in incidents if i.status == "Resolved"]
    if resolved_incidents:
        pct_reports_completed = (
            sum(1 for i in resolved_incidents if i.is_completed)
            / len(resolved_incidents)
            * 100
        )
    else:
        pct_reports_completed = 0.0

    return PeriodStats(
        start=start,
        end=end,
        total_incidents=len(incidents),
        total_entities=total_entities,
        top_entities=top_entities,
        severity_counts=severity_counts,
        service_total_count=service_total_count,
        service_resolved_count=service_resolved_count,
        service_status_counts=service_status_counts,
        product_total_count=product_total_count,
        product_resolved_count=product_resolved_count,
        product_status_counts=product_status_counts,
        service_detection_method_counts=service_detection_method_counts,
        product_detection_method_counts=product_detection_method_counts,
        mean_action_items=mean_action_items,
        pct_reports_completed=pct_reports_completed,
        service_mean_tt_dec=mean_timedelta([i.tt_declared for i in service]),
        service_mean_tt_alert=mean_timedelta([i.tt_alerted for i in service]),
        service_mean_tt_resp=mean_timedelta([i.tt_responded for i in service]),
        service_mean_tt_mit=mean_timedelta([i.tt_mitigated for i in service]),
        service_mean_tt_res=mean_timedelta([i.tt_resolved for i in service_resolved]),
        service_pvariance_tt_dec=pvariance_timedelta([i.tt_declared for i in service]),
        service_pvariance_tt_alert=pvariance_timedelta([i.tt_alerted for i in service]),
        service_pvariance_tt_resp=pvariance_timedelta(
            [i.tt_responded for i in service]
        ),
        service_pvariance_tt_mit=pvariance_timedelta([i.tt_mitigated for i in service]),
        service_pvariance_tt_res=pvariance_timedelta(
            [i.tt_resolved for i in service_resolved]
        ),
        service_count_tt_dec=count_timedelta([i.tt_declared for i in service]),
        service_count_tt_alert=count_timedelta([i.tt_alerted for i in service]),
        service_count_tt_resp=count_timedelta([i.tt_responded for i in service]),
        service_count_tt_mit=count_timedelta([i.tt_mitigated for i in service]),
        service_count_tt_res=count_timedelta([i.tt_resolved for i in service_resolved]),
        product_mean_tt_dec=mean_timedelta([i.tt_declared for i in product]),
        product_mean_tt_alert=mean_timedelta([i.tt_alerted for i in product]),
        product_mean_tt_resp=mean_timedelta([i.tt_responded for i in product]),
        product_mean_tt_mit=mean_timedelta([i.tt_mitigated for i in product]),
        product_mean_tt_res=mean_timedelta([i.tt_resolved for i in product_resolved]),
        product_pvariance_tt_dec=pvariance_timedelta([i.tt_declared for i in product]),
        product_pvariance_tt_alert=pvariance_timedelta([i.tt_alerted for i in product]),
        product_pvariance_tt_resp=pvariance_timedelta(
            [i.tt_responded for i in product]
        ),
        product_pvariance_tt_mit=pvariance_timedelta([i.tt_mitigated for i in product]),
        product_pvariance_tt_res=pvariance_timedelta(
            [i.tt_resolved for i in product_resolved]
        ),
        product_count_tt_dec=count_timedelta([i.tt_declared for i in product]),
        product_count_tt_alert=count_timedelta([i.tt_alerted for i in product]),
        product_count_tt_resp=count_timedelta([i.tt_responded for i in product]),
        product_count_tt_mit=count_timedelta([i.tt_mitigated for i in product]),
        product_count_tt_res=count_timedelta([i.tt_resolved for i in product_resolved]),
    )


def compute_period_comparison(
    incidents,
    current_start: str,
    current_end: str,
    prior_start: str,
    prior_end: str,
) -> PeriodComparison:
    current_incidents = [
        i
        for i in incidents
        if i.declare_date and current_start <= i.declare_date < current_end
    ]
    prior_incidents = [
        i
        for i in incidents
        if i.declare_date and prior_start <= i.declare_date < prior_end
    ]

    return PeriodComparison(
        current=build_period_stats(current_incidents, current_start, current_end),
        prior=build_period_stats(prior_incidents, prior_start, prior_end),
    )
