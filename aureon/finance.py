"""Financial reconciliation and scenario forecasting from the local ledger."""
import math
from .workflows import add_finance_entry,finance_summary
def record_transaction(db_path,entry_type,amount,currency,description,reference=None,actual=True):
 return add_finance_entry(db_path,entry_type,amount,currency,description,reference,actual)
def reconcile(db_path,currency,opening_balance,closing_balance):
 if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha():raise ValueError("currency must be three letters")
 for v in (opening_balance,closing_balance):
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError("balances must be finite numbers")
 net=finance_summary(db_path).get(currency.upper(),{}).get("actual_net",0.0)
 expected=round(opening_balance+net,2)
 return {"currency":currency.upper(),"opening_balance":round(opening_balance,2),"recorded_net_movement":net,
 "expected_closing_balance":expected,"provided_closing_balance":round(closing_balance,2),
 "unexplained_difference":round(closing_balance-expected,2),"reconciled":abs(closing_balance-expected)<0.01,
 "warning":"Uses manually recorded entries and balances; no bank or payment-provider connection."}
def cashflow_projection(db_path,opening_cash,forecast_days=30,expected_revenue=0,expected_costs=0,currency="USD"):
 vals=(opening_cash,expected_revenue,expected_costs)
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):raise ValueError("cashflow values must be finite numbers")
 if expected_revenue<0 or expected_costs<0:raise ValueError("forecast inflows and outflows must be non-negative")
 if not isinstance(forecast_days,int) or isinstance(forecast_days,bool) or not 1<=forecast_days<=365:raise ValueError("forecast_days must be 1..365")
 if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha():raise ValueError("currency must be three letters")
 return {"currency":currency.upper(),"days":forecast_days,"opening_cash":round(opening_cash,2),
 "expected_revenue":round(expected_revenue,2),"expected_costs":round(expected_costs,2),
 "projected_closing_cash":round(opening_cash+expected_revenue-expected_costs,2),
 "assumption":"Scenario only; user-entered estimates, no prediction, timing, tax or FX feed."}
def financial_dashboard(db_path):
 return {"ledger":finance_summary(db_path),"actual_and_estimated_separated":True}
