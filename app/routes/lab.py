from fastapi import APIRouter, Request
from app.main import templates, get_sidebar_context

router = APIRouter()


@router.get("/lab-page")
async def lab_page(request: Request):
    return templates.TemplateResponse(request, "lab.html", {
        "active_page": "lab",
        "user": request.state.user,
        **get_sidebar_context(),
    })
