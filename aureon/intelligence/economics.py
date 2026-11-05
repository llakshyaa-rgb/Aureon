"""Transparent unit economics for POD and dropshipping offers."""
from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class Offer:
    channel: str
    selling_price: float
    product_cost: float
    shipping_cost: float = 0.0
    packaging_cost: float = 0.0
    platform_fee_rate: float = 0.0
    payment_fee_rate: float = 0.0
    payment_fixed_fee: float = 0.0
    estimated_ad_cost: float = 0.0
    other_costs: float = 0.0
    duty_cost: float = 0.0
    tax_rate: float = 0.0
    return_rate: float = 0.0
    chargeback_rate: float = 0.0
    currency: str = "USD"

    def validate(self):
        if not isinstance(self.channel, str) or not self.channel.strip():
            raise ValueError("channel is required")
        names = (
            "selling_price", "product_cost", "shipping_cost", "packaging_cost",
            "platform_fee_rate", "payment_fee_rate", "payment_fixed_fee",
            "estimated_ad_cost", "other_costs", "duty_cost",
            "tax_rate", "return_rate", "chargeback_rate",
        )
        for name in names:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(name + " must be finite and non-negative")
        if self.selling_price <= 0:
            raise ValueError("selling_price must be greater than zero")
        if any(getattr(self, name) > 1 for name in
               ("platform_fee_rate", "payment_fee_rate", "tax_rate", "return_rate", "chargeback_rate")):
            raise ValueError("fee, tax, return and chargeback rates must be fractions between 0 and 1")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Za-z]{3}", self.currency):
            raise ValueError("currency must be a three-letter code")


def calculate_unit_economics(offer):
    offer.validate()
    platform_fee = offer.selling_price * offer.platform_fee_rate
    payment_fee = offer.selling_price * offer.payment_fee_rate + offer.payment_fixed_fee
    fulfilment = offer.product_cost + offer.shipping_cost + offer.packaging_cost + offer.duty_cost
    estimated_tax = offer.selling_price * offer.tax_rate
    return_reserve = offer.selling_price * offer.return_rate
    chargeback_reserve = offer.selling_price * offer.chargeback_rate
    total = (fulfilment + platform_fee + payment_fee + estimated_tax + return_reserve +
             chargeback_reserve + offer.estimated_ad_cost + offer.other_costs)
    profit = offer.selling_price - total
    break_even = max(0.0, offer.selling_price - fulfilment - platform_fee - payment_fee -
                     estimated_tax - return_reserve - chargeback_reserve - offer.other_costs)
    return {
        "channel": offer.channel,
        "currency": offer.currency.upper(),
        "selling_price": round(offer.selling_price, 2),
        "fulfilment_cost": round(fulfilment, 2),
        "platform_fee": round(platform_fee, 2),
        "payment_fee": round(payment_fee, 2),
        "estimated_tax": round(estimated_tax, 2),
        "return_reserve": round(return_reserve, 2),
        "chargeback_reserve": round(chargeback_reserve, 2),
        "duty_cost": round(offer.duty_cost, 2),
        "advertising_cost": round(offer.estimated_ad_cost, 2),
        "other_costs": round(offer.other_costs, 2),
        "total_cost": round(total, 2),
        "estimated_profit": round(profit, 2),
        "profit_margin": round(profit / offer.selling_price, 8),
        "break_even_ad_cost": round(break_even, 2),
        "profitable_before_ads": profit + offer.estimated_ad_cost > 0,
        "assumptions": [
            "All inputs use the same currency.",
            "Tax, duty, return and chargeback reserves are estimates supplied by the operator.",
            "FX, tax treatment and statutory duties must be verified for each market.",
            "Supplier and platform fees are estimates until verified with live quotes.",
        ],
    }


def compare_channels(pod, dropshipping):
    if not isinstance(pod, Offer) or not isinstance(dropshipping, Offer):
        raise ValueError("both channels must be Offer objects")
    if pod.currency.upper() != dropshipping.currency.upper():
        raise ValueError("POD and dropshipping offers must use the same currency")
    ranked = sorted(
        [calculate_unit_economics(pod), calculate_unit_economics(dropshipping)],
        key=lambda x: (x["estimated_profit"], x["profit_margin"]),
        reverse=True,
    )
    return {
        "recommended_channel": ranked[0]["channel"] if ranked[0]["estimated_profit"] > 0 else "neither",
        "ranking": ranked,
        "warning": "This is a cost comparison, not a demand forecast or profit guarantee.",
    }
