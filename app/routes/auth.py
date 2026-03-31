import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.main import templates, serializer, USERS

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {
        "error": None,
    })


@router.post("/login")
async def login_submit(request: Request, username: str = Form(), password: str = Form()):
    user = USERS.get(username)
    if user and password == os.getenv(user["password_env"], ""):
        session_data = {"username": username, "role": user["role"]}
        signed = serializer.dumps(session_data)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            "session", signed,
            httponly=True, samesite="lax", secure=True, max_age=86400,
        )
        return response

    return templates.TemplateResponse(request, "login.html", {
        "error": "Invalid username or password.",
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session")
    return response
