from fastapi import APIRouter, Request
from app.main import templates, get_dhan_client, get_sidebar_context

router = APIRouter()


@router.get("/")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html", {
        "active_page": "home",
        "user": request.state.user,
        **get_sidebar_context(),
    })


@router.get("/api/fund-limits")
async def fund_limits(request: Request):
    dhan = get_dhan_client()
    if not dhan:
        return templates.TemplateResponse(request, "partials/fund_limits.html", {
            "error": "No access token. Generate one in Authentication.",
            "metrics": None,
        })

    try:
        resp = dhan.get_fund_limits()
        if resp.get("status") == "success":
            data = resp.get("data", {})
            metrics = {k: v for k, v in data.items() if k != "dhanClientId"}
            return templates.TemplateResponse(request, "partials/fund_limits.html", {
                "metrics": metrics,
                "error": None,
            })
        else:
            return templates.TemplateResponse(request, "partials/fund_limits.html", {
                "error": f"Failed: {resp.get('remarks')}",
                "metrics": None,
            })
    except Exception as e:
        return templates.TemplateResponse(request, "partials/fund_limits.html", {
            "error": str(e),
            "metrics": None,
        })
