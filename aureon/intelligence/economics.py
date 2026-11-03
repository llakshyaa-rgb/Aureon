"""Transparent unit economics for POD and dropshipping offers."""
from dataclasses import dataclass

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
    currency: str = "USD"

    def validate(self):
        values = (self.selling_price, self.product_cost, self.shipping_cost,
                  self.packaging_cost, self.platform_fee_rate, self.payment_fee_rate,
                  self.payment_fixed_fee, self.estimated_ad_cost, self.other_costs)
        if any(float(value) < 0 for value in values):
            raise ValueError("price, costs, and fee rates cannot be negative")
        if self.selling_price <= 0:
            raise ValueError("selling_price must be greater than zero")
        if self.platform_fee_rate > 1 or self.payment_fee_rate > 1:
            raise ValueError("fee rates must be fractions between 0 and 1")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("currency must be a three-letter code")

def calculate_unit_economics(offer: Offer):
    offer.validate()
    platform_fee = offer.selling_price * offer.platform_fee_rate
    payment_fee = offer.selling_price * offer.payment_fee_rate + offer.payment_fixed_fee
    fulfilment = offer.product_cost + offer.shipping_cost + offer.packaging_cost
    total_cost = fulfilment + platform_fee + payment_fee + offer.estimated_ad_cost + offer.other_costs
    profit = offer.selling_price - total_cost
    break_even_ad_cost = max(0.0, offer.selling_price - fulfilment - platform_fee - payment_fee - offer.other_costs)
    return {
        "channel": offer.channel, "currency": offer.currency.upper(),
        "selling_price": round(offer.selling_price, 2),
        "fulfilment_cost": round(fulfilment, 2),
        "platform_fee": round(platform_fee, 2), "payment_fee": round(payment_fee, 2),
        "advertising_cost": round(offer.estimated_ad_cost, 2),
        "other_costs": round(offer.other_costs, 2), "total_cost": round(total_cost, 2),
        "estimated_profit": round(profit, 2), "profit_margin": round(profit / offer.selling_price, 4),
        "break_even_ad_cost": round(break_even_ad_cost, 2),
        "profitable_before_ads": offer.selling_price - (total_cost - offer.estimated_ad_cost) > 0,
        "assumptions": ["All inputs use the same currency.",
          "Taxes, duties, refunds, chargebacks, and FX are excluded unless entered as other_costs.",
          "Supplier and platform fees are estimates until verified with live quotes."]
    }

def compare_channels(pod: Offer, dropshipping: Offer):
    if pod.currency.upper() != dropshipping.currency.upper():
        raise ValueError("POD and dropshipping offers must use the same currency")
    ranked = sorted([calculate_unit_economics(pod), calculate_unit_economics(dropshipping)],
                    key=lambda item: (item["estimated_profit"], item["profit_margin"]), reverse=True)
    return {"recommended_channel": ranked[0]["channel"] if ranked[0]["estimated_profit"] > 0 else "neither",
            "ranking": ranked,
            "warning": "This is a cost comparison, not a demand forecast or profit guarantee."}
