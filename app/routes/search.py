import asyncio

from fastapi import APIRouter, Request
from app.main import templates, load_config, get_sidebar_context
from instruments_search import smart_search, update_database

router = APIRouter()


@router.get("/search")
async def search_page(request: Request):
    config = load_config()
    last_update = config.get("last_database_update", "Never")
    return templates.TemplateResponse(request, "search.html", {
        "active_page": "search",
        "user": request.state.user,
        "last_update": last_update,
        **get_sidebar_context(),
    })


@router.get("/api/search")
async def search_instruments(request: Request, q: str = ""):
    if not q or len(q) < 2:
        return templates.TemplateResponse(request, "partials/search_results.html", {
            "results": [],
            "query": q,
            "error": None,
        })

    results = await asyncio.to_thread(smart_search, q)
    if isinstance(results, str) and results.startswith("Error:"):
        return templates.TemplateResponse(request, "partials/search_results.html", {
            "results": [],
            "query": q,
            "error": results,
        })

    return templates.TemplateResponse(request, "partials/search_results.html", {
        "results": results,
        "query": q,
        "error": None,
    })


@router.post("/api/update-db")
async def update_db(request: Request):
    if request.state.user["role"] != "admin":
        return "<p class='error'>Admin access required.</p>"

    try:
        await asyncio.to_thread(update_database)
        config = load_config()
        last_update = config.get("last_database_update", "Unknown")
        return f"<p class='success'>Database updated successfully. Last update: {last_update}</p>"
    except Exception as e:
        return f"<p class='error'>Failed: {e}</p>"
