"""
finance_ops — deterministic finance / accounting / tax MATH, so AVA computes exactly instead of
doing arithmetic in her head. Actions:
  - journal_entry      : double-entry check (debits == credits)
  - depreciate         : straight-line or MACRS schedule
  - self_employment_tax: 15.3% SS + Medicare, half deductible
  - federal_income_tax : bracket math (marginal + effective rate)
  - amortize           : loan amortization (monthly payment, total interest)
Year-specific defaults (tax brackets, Social Security wage base) are LABELED with their tax year;
pass current-year values to override. This is a CALCULATOR, not tax advice.
"""
from __future__ import annotations
from typing import Any, Dict
from ..tool_registry import Tool, register

# MACRS GDS, half-year convention — % of basis per year (IRS Publication 946 tables; these are fixed).
_MACRS = {
    3:  [33.33, 44.45, 14.81, 7.41],
    5:  [20.00, 32.00, 19.20, 11.52, 11.52, 5.76],
    7:  [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46],
    10: [10.00, 18.00, 14.40, 11.52, 9.22, 7.37, 6.55, 6.55, 6.56, 6.55, 3.28],
    15: [5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 2.95],
    20: [3.750, 7.219, 6.677, 6.177, 5.713, 5.285, 4.888, 4.522, 4.462, 4.461, 4.462, 4.461,
         4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 2.231],
}

# Federal ordinary-income brackets — 2024 tax year (LABELED). Pass args.brackets for another year.
_BRACKETS_2024 = {
    "single":           [[0.10, 11600], [0.12, 47150], [0.22, 100525], [0.24, 191950], [0.32, 243725], [0.35, 609350], [0.37, None]],
    "married_joint":    [[0.10, 23200], [0.12, 94300], [0.22, 201050], [0.24, 383900], [0.32, 487450], [0.35, 731200], [0.37, None]],
    "married_separate": [[0.10, 11600], [0.12, 47150], [0.22, 100525], [0.24, 191950], [0.32, 243725], [0.35, 365600], [0.37, None]],
    "head_of_household":[[0.10, 16550], [0.12, 63100], [0.22, 100500], [0.24, 191950], [0.32, 243700], [0.35, 609350], [0.37, None]],
}
_SS_WAGE_BASE_2024 = 168600.0


def _money(x):
    return round(float(x), 2)


def _journal_entry(args):
    lines = args.get("lines") or args.get("entries") or []
    if not isinstance(lines, list) or not lines:
        return {"status": "error", "message": "Provide lines: [{account, debit, credit}, ...]"}
    td = tc = 0.0
    rows = []
    for ln in lines:
        d = float(ln.get("debit") or 0)
        c = float(ln.get("credit") or 0)
        td += d
        tc += c
        rows.append({"account": ln.get("account", ""), "debit": _money(d), "credit": _money(c)})
    balanced = round(td, 2) == round(tc, 2)
    return {"status": "ok", "balanced": balanced, "total_debits": _money(td), "total_credits": _money(tc),
            "difference": _money(td - tc), "lines": rows,
            "note": "Balanced: debits equal credits." if balanced else "NOT balanced — debits and credits differ."}


def _depreciate(args):
    cost = float(args.get("cost") or 0)
    salvage = float(args.get("salvage") or 0)
    method = (args.get("method") or "straight_line").lower()
    if cost <= 0:
        return {"status": "error", "message": "Provide cost > 0."}
    sched = []
    if method in ("straight_line", "sl", "straight-line"):
        life = int(args.get("life") or args.get("years") or 0)
        if life <= 0:
            return {"status": "error", "message": "Provide life (years) for straight-line."}
        annual = (cost - salvage) / life
        book = cost
        for y in range(1, life + 1):
            book -= annual
            sched.append({"year": y, "depreciation": _money(annual), "book_value": _money(max(book, salvage))})
        return {"status": "ok", "method": "straight_line", "annual_depreciation": _money(annual), "schedule": sched}
    if method in ("macrs", "m"):
        cls = int(args.get("macrs_class") or args.get("life") or 0)
        pct = _MACRS.get(cls)
        if not pct:
            return {"status": "error", "message": f"MACRS class must be one of {sorted(_MACRS)} (years). Got {cls}."}
        book = cost
        total = 0.0
        for i, p in enumerate(pct, start=1):
            dep = cost * p / 100.0
            total += dep
            book -= dep
            sched.append({"year": i, "rate_pct": p, "depreciation": _money(dep), "book_value": _money(book)})
        return {"status": "ok", "method": f"MACRS {cls}-year (half-year convention, IRS Pub 946)",
                "total_depreciated": _money(total), "schedule": sched,
                "note": "MACRS ignores salvage value and recovers the full basis."}
    return {"status": "error", "message": "method must be 'straight_line' or 'macrs'."}


def _self_employment_tax(args):
    net = float(args.get("net_earnings") or args.get("net") or 0)
    wage_base = float(args.get("ss_wage_base") or _SS_WAGE_BASE_2024)
    if net <= 0:
        return {"status": "ok", "se_tax": 0.0, "note": "No net self-employment earnings."}
    taxable = net * 0.9235
    ss = min(taxable, wage_base) * 0.124
    medicare = taxable * 0.029
    se_tax = ss + medicare
    return {"status": "ok", "net_earnings": _money(net), "taxable_base_92_35pct": _money(taxable),
            "social_security_12_4pct": _money(ss), "medicare_2_9pct": _money(medicare),
            "se_tax": _money(se_tax), "one_half_deductible": _money(se_tax / 2), "ss_wage_base_used": wage_base,
            "note": "SS wage base default is the 2024 figure ($168,600) — pass ss_wage_base for another year. "
                    "Excludes the additional 0.9% Medicare tax above high-income thresholds."}


def _federal_income_tax(args):
    ti = float(args.get("taxable_income") or 0)
    status = (args.get("filing_status") or "single").lower().replace(" ", "_").replace("-", "_")
    status = {"mfj": "married_joint", "married_filing_jointly": "married_joint", "mfs": "married_separate",
              "hoh": "head_of_household"}.get(status, status)
    supplied = args.get("brackets")
    brackets = supplied or _BRACKETS_2024.get(status)
    if not brackets:
        return {"status": "error", "message": f"Unknown filing_status '{status}'. Use single, married_joint, "
                                              "married_separate, head_of_household, or pass brackets."}
    tax = 0.0
    lower = 0.0
    marginal = 0.0
    for rate, upto in brackets:
        cap = float("inf") if upto in (None, "inf", "") else float(upto)
        if ti > lower:
            taxed = min(ti, cap) - lower
            tax += taxed * float(rate)
            marginal = float(rate)
        lower = cap
        if ti <= cap:
            break
    eff = tax / ti if ti > 0 else 0
    return {"status": "ok", "taxable_income": _money(ti), "filing_status": status,
            "federal_income_tax": _money(tax), "marginal_rate": marginal, "effective_rate": round(eff, 4),
            "note": ("Brackets used: 2024 tax-year defaults — pass args.brackets with current-year values for another year."
                     if not supplied else "Brackets supplied by caller.")}


def _amortize(args):
    principal = float(args.get("principal") or 0)
    annual_rate = float(args.get("annual_rate") or args.get("rate") or 0)
    years = float(args.get("years") or 0)
    months = int(args.get("months") or (years * 12 if years else 0))
    if principal <= 0 or months <= 0:
        return {"status": "error", "message": "Provide principal > 0 and years (or months)."}
    r = annual_rate / 100.0 / 12.0
    payment = principal / months if r == 0 else principal * r / (1 - (1 + r) ** (-months))
    total = payment * months
    return {"status": "ok", "principal": _money(principal), "annual_rate_pct": annual_rate, "months": months,
            "monthly_payment": _money(payment), "total_paid": _money(total), "total_interest": _money(total - principal)}


_ACTIONS = {
    "journal_entry": _journal_entry,
    "depreciate": _depreciate, "depreciation": _depreciate,
    "self_employment_tax": _self_employment_tax, "se_tax": _self_employment_tax,
    "federal_income_tax": _federal_income_tax, "income_tax": _federal_income_tax,
    "amortize": _amortize, "loan": _amortize,
}


def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"preview": f"finance_ops {args.get('action', '')}", "args": args}


def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    action = (args.get("action") or "").lower()
    fn = _ACTIONS.get(action)
    if not fn:
        return {"status": "error", "message": "Unknown action. Use: journal_entry, depreciate, self_employment_tax, federal_income_tax, amortize."}
    if dry_run:
        return {"status": "dry-run", "message": f"Would compute {action}"}
    try:
        return fn(args)
    except Exception as e:
        return {"status": "error", "message": str(e)}


TOOL = Tool(
    name="finance_ops",
    summary=(
        "Deterministic finance/accounting/tax MATH — use this instead of mental arithmetic. Actions: "
        "journal_entry (args.lines=[{account,debit,credit}] -> checks debits==credits); "
        "depreciate (args.cost, salvage, method='straight_line'|'macrs', life or macrs_class in years -> schedule); "
        "self_employment_tax (args.net_earnings -> 15.3% SS+Medicare, half deductible); "
        "federal_income_tax (args.taxable_income, filing_status, optional args.brackets -> tax + marginal/effective rate); "
        "amortize (args.principal, annual_rate, years -> monthly payment + total interest). "
        "Year-specific defaults (tax brackets and SS wage base = 2024) are labeled; pass current-year values to override. "
        "It computes; it does NOT give tax advice."
    ),
    plan=_plan,
    run=_run,
)
register(TOOL)
