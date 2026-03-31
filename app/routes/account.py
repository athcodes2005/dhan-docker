from fastapi import APIRouter, Request
from app.main import (
    templates, get_dhan_client, get_sidebar_context,
    load_portfolio_history, save_portfolio_snapshot,
)

router = APIRouter()


@router.get("/account")
async def account_page(request: Request):
    return templates.TemplateResponse(request, "account.html", {
        "active_page": "account",
        "user": request.state.user,
        **get_sidebar_context(),
    })


@router.get("/api/holdings")
async def holdings(request: Request):
    dhan = get_dhan_client()
    if not dhan:
        return templates.TemplateResponse(request, "partials/holdings.html", {
            "error": "No access token. Generate one in Authentication.",
            "holdings": None,
            "summary": None,
            "history": None,
        })

    try:
        resp = dhan.get_holdings()
        if resp.get("status") == "success":
            data = resp.get("data", [])
            if not data:
                return templates.TemplateResponse(request, "partials/holdings.html", {
                    "error": None,
                    "holdings": [],
                    "summary": None,
                    "history": None,
                })

            invested = 0.0
            nav = 0.0
            for h in data:
                qty = h.get("totalQty", 0)
                avg = h.get("avgCostPrice", 0)
                ltp = h.get("lastTradedPrice", 0)
                h["investedValue"] = round(qty * avg, 2)
                h["currentValue"] = round(qty * ltp, 2)
                invested += qty * avg
                nav += qty * ltp

            invested = round(invested, 2)
            nav = round(nav, 2)
            pnl = round(nav - invested, 2)
            pnl_pct = round((pnl / invested) * 100, 2) if invested else 0

            save_portfolio_snapshot(invested, nav)
            history = load_portfolio_history()

            return templates.TemplateResponse(request, "partials/holdings.html", {
                "error": None,
                "holdings": data,
                "summary": {
                    "invested": invested,
                    "nav": nav,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                },
                "history": history,
            })
        else:
            return templates.TemplateResponse(request, "partials/holdings.html", {
                "error": f"Failed: {resp.get('remarks')}",
                "holdings": None,
                "summary": None,
                "history": None,
            })
    except Exception as e:
        return templates.TemplateResponse(request, "partials/holdings.html", {
            "error": str(e),
            "holdings": None,
            "summary": None,
            "history": None,
        })


@router.get("/api/positions")
async def positions(request: Request):
    dhan = get_dhan_client()
    if not dhan:
        return templates.TemplateResponse(request, "partials/positions.html", {
            "error": "No access token. Generate one in Authentication.",
            "positions": None,
        })

    try:
        resp = dhan.get_positions()
        if resp.get("status") == "success":
            data = resp.get("data", [])
            return templates.TemplateResponse(request, "partials/positions.html", {
                "error": None,
                "positions": data,
            })
        else:
            return templates.TemplateResponse(request, "partials/positions.html", {
                "error": f"Failed: {resp.get('remarks')}",
                "positions": None,
            })
    except Exception as e:
        return templates.TemplateResponse(request, "partials/positions.html", {
            "error": str(e),
            "positions": None,
        })
