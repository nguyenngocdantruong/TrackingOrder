"""Provider-aware shipment stages. Pure functions: no database or network access.

Add event codes to a provider profile, or register a new profile below. Description
rules are only for providers whose codes are ambiguous; never infer a delivery
hub from an arbitrary warehouse name. See docs/notification-stages.md.
"""
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional
import unicodedata


STAGE_CHOICES = (
    ('preparing', 'Tiếp nhận / Chuẩn bị'),
    ('picked_up', 'Đã lấy / nhận hàng'),
    ('in_transit', 'Đang vận chuyển'),
    ('at_delivery_station', 'Đến trạm giao hàng'),
    ('out_for_delivery', 'Đang giao hàng'),
    ('delivered', 'Đã giao'),
)
STAGE_IDS = tuple(stage for stage, _ in STAGE_CHOICES)
STAGE_LABELS = dict(STAGE_CHOICES)


def selected_stages(settings):
    """Missing/null preferences mean all; an explicit empty list means none."""
    value = (settings or {}).get('notifyStages')
    if value is None:
        return list(STAGE_IDS)
    if not isinstance(value, (list, tuple)):
        return []
    return [stage for stage in STAGE_IDS if stage in value]


def _text(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).casefold().split())


@dataclass(frozen=True)
class StageProfile:
    codes: Mapping[str, str]
    milestones: Mapping[str, str] = field(default_factory=dict)
    # A matched rule returning None explicitly marks an ambiguous event unknown.
    rules: tuple[tuple[Callable[[dict], bool], Optional[str]], ...] = ()


def _description_contains(*phrases):
    def matches(event):
        description = _text(event.get('descBuyer') or event.get('descSeller'))
        return any(phrase in description for phrase in phrases)
    return matches


PROFILES = {
    'shopee_express_vn': StageProfile(
        codes={
            'a000': 'preparing', 'f000': 'preparing', 'f001': 'preparing',
            'f098': 'picked_up', 'f100': 'picked_up',
            **dict.fromkeys(('f440', 'f441', 'f445', 'f450', 'f510', 'f515',
                             'f540', 'f541', 'f580'), 'in_transit'),
            'f599': 'at_delivery_station', 'f598': 'at_delivery_station',
            'f600': 'out_for_delivery', 'f980': 'delivered',
        },
        milestones={'1': 'preparing', '5': 'in_transit',
                    '6': 'out_for_delivery', '8': 'delivered'},
    ),
    'lex': StageProfile(codes={
        'cb_pre_accept': 'preparing',
        **dict.fromkeys((
            'cb_pre_transport', 'cb_pre_delivering', 'cb_pre_sign',
            'cb_sign_in_success', 'cb_ib_success_in_sort_center',
            'cb_ob_success_in_sort_center', 'cb_handover', 'cb_uplifted',
            'cb_linehaul_arrival_success', 'cb_customs_clearance_success',
            'cb_submit_to_custom', 'domestic_ib_success_in_sort_center',
            'domestic_linehaul_packed', 'domestic_ob_success_in_sort_center',
        ), 'in_transit'),
        'domestic_package_stationed_in': 'at_delivery_station',
        **dict.fromkeys((
            'domestic_package_stationed_out', 'domestic_out_for_delivery',
            'domestic_about_to_deliver', 'domestic_redelivery',
            'domestic_1st_attempt_failed',
        ), 'out_for_delivery'),
        'domestic_delivered': 'delivered',
    }),
    'jt_express': StageProfile(
        codes={'delivered': 'delivered', 'picked_up': 'picked_up',
               'in_transit': 'in_transit'},
        rules=(
            # These are not successful pickup/delivery events despite old codes.
            (_description_contains('kiện vấn đề', 'hoàn hàng', 'đã hủy',
                                   'chưa ký nhận', 'chưa giao', 'không thành công'), None),
            (_description_contains('đơn hàng đã ký nhận', 'người ký nhận là'), 'delivered'),
            (_description_contains('đang giao hàng'), 'out_for_delivery'),
            (_description_contains('đã nhận hàng'), 'picked_up'),
        ),
    ),
}

# Exact semantic names only. Numeric milestones are provider-specific (LEX uses
# zero for every event), and a shipment's latest status cannot classify old events.
COMMON_NAMES = {
    'preparing to ship': 'preparing', 'đang tiếp nhận': 'preparing',
    'picked up': 'picked_up', 'đã nhận hàng': 'picked_up',
    'in transit': 'in_transit', 'đang vận chuyển': 'in_transit',
    'enter last mile hub': 'at_delivery_station',
    'out for delivery': 'out_for_delivery', 'đang giao hàng': 'out_for_delivery',
    'delivered': 'delivered', 'đã giao': 'delivered',
}


def classify_event(carrier_id, event):
    """Return a stable stage ID, or None when the event cannot be classified."""
    profile = PROFILES.get(carrier_id)
    if profile:
        for matches, stage in profile.rules:
            if matches(event):
                return stage
        stage = profile.codes.get(_text(event.get('code')))
        if stage:
            return stage
        stage = profile.milestones.get(str(event.get('milestoneCode')))
        if stage:
            return stage
    for key in ('name', 'milestoneName'):
        stage = COMMON_NAMES.get(_text(event.get(key)))
        if stage:
            return stage
    return None


def wants_stage(settings, stage):
    selected = selected_stages(settings)
    # Preserve existing notifications for users opting into everything, including
    # new/exception codes. A partial selection never guesses an unknown stage.
    return stage in selected if stage else set(selected) == set(STAGE_IDS)
