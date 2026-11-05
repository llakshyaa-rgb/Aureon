"""Scenario analysis and transparent pricing recommendations."""
import math
from dataclasses import replace
from .economics import Offer, calculate_unit_economics


def pricing_scenarios(offer, prices=None, target_margin=0.25):
    if not isinstance(offer, Offer):
        raise ValueError("offer must be an Offer")
    offer.validate()
    if isinstance(target_margin, bool) or not isinstance(target_margin, (int, float)) or not math.isfinite(target_margin) or not 0 <= target_margin < 0.95:
        raise ValueError("target_margin must be between 0 and 0.95")
    if prices is None:
        prices = [round(offer.selling_price * factor, 2) for factor in (0.8, 0.9, 1.0, 1.1, 1.2)]
    if not isinstance(prices, list) or not 1 <= len(prices) <= 30:
        raise ValueError("prices must contain 1-30 values")
    scenarios = []
    for price in prices:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("each scenario price must be positive and finite")
        result = calculate_unit_economics(replace(offer, selling_price=float(price)))
        scenarios.append(result)
    fixed_cost = offer.product_cost + offer.shipping_cost + offer.packaging_cost + offer.duty_cost + offer.payment_fixed_fee + offer.other_costs
    variable_rate = offer.platform_fee_rate + offer.payment_fee_rate + offer.tax_rate + offer.return_rate + offer.chargeback_rate
    denominator = 1 - variable_rate - target_margin
    target_price = round(fixed_cost / denominator, 2) if denominator > 0 else None
    return {"currency": offer.currency.upper(), "target_margin": target_margin,
            "target_price": target_price, "scenarios": scenarios,
            "best_scenario": max(scenarios, key=lambda x: x["estimated_profit"]),
            "warning": "Scenario math only. Does not establish demand, tax, duty, FX or verified fees."}


def break_even_orders(fixed_costs, contribution_per_order):
    for value, name in ((fixed_costs, "fixed_costs"), (contribution_per_order, "contribution_per_order")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(name + " must be finite")
    if fixed_costs < 0 or contribution_per_order <= 0:
        raise ValueError("fixed_costs must be non-negative and contribution_per_order positive")
    return {"orders": math.ceil(fixed_costs / contribution_per_order),
            "fixed_costs": round(fixed_costs, 2),
            "contribution_per_order": round(contribution_per_order, 2),
            "warning": "Assumes contribution per order remains constant."}
