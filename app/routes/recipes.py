"""All recipe pages: list/search, detail, create, edit, delete.

Routes stay thin: read the request, call the repository, render a template.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import repository
from ..security import current_user
from ..templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", tag: str = "", partial: int = 0):
    """Home page: the searchable, filterable list of recipes.

    Query parameters (all optional, taken from the URL ``?q=...&tag=...``):
        q       : free-text search across title, ingredients, tags, description.
        tag     : show only recipes containing this tag.
        partial : when 1, return ONLY the list fragment (no page shell). The
                  live-search JavaScript uses this to swap results in-place.
    """
    recipes = repository.search_recipes(q, tag)
    if partial:
        return templates.TemplateResponse(
            "partials/list.html", {"request": request, "recipes": recipes}
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recipes": recipes,
            "q": q,
            "tags": repository.all_tags(),
            "active_tag": tag,
        },
    )


@router.get("/recipe/new", response_class=HTMLResponse)
def new_form(request: Request):
    """Empty "add a recipe" form. ``r=None`` tells the template it's a create."""
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        "form.html", {"request": request, "r": None, "action": "/recipe/new"}
    )


@router.post("/recipe/new")
def create(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    prep_time: str = Form(""),
    cook_time: str = Form(""),
    servings: str = Form(""),
    ingredients: str = Form(""),
    instructions: str = Form(""),
    notes: str = Form(""),
    tags: str = Form(""),
    source_url: str = Form(""),
):
    """Save the submitted form as a new recipe, then redirect (303) to it so a
    browser refresh does not re-submit the form (Post/Redirect/Get)."""
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    rid = repository.create_recipe({
        "title": title, "description": description, "prep_time": prep_time,
        "cook_time": cook_time, "servings": servings, "ingredients": ingredients,
        "instructions": instructions, "notes": notes, "tags": tags,
        "source_url": source_url,
    })
    return RedirectResponse(f"/recipe/{rid}", status_code=303)


@router.get("/recipe/{rid}", response_class=HTMLResponse)
def detail(request: Request, rid: int):
    """Show one recipe; unknown ids just bounce back to the home page."""
    r = repository.get_recipe(rid)
    if r is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("recipe.html", {"request": request, "r": r})


@router.get("/recipe/{rid}/edit", response_class=HTMLResponse)
def edit_form(request: Request, rid: int):
    """The same form.html as "new", pre-filled with the existing recipe."""
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    r = repository.get_recipe(rid)
    if r is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "form.html", {"request": request, "r": r, "action": f"/recipe/{rid}/edit"}
    )


@router.post("/recipe/{rid}/edit")
def update(
    request: Request,
    rid: int,
    title: str = Form(...),
    description: str = Form(""),
    prep_time: str = Form(""),
    cook_time: str = Form(""),
    servings: str = Form(""),
    ingredients: str = Form(""),
    instructions: str = Form(""),
    notes: str = Form(""),
    tags: str = Form(""),
    source_url: str = Form(""),
):
    """Save edits to an existing recipe."""
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    repository.update_recipe(rid, {
        "title": title, "description": description, "prep_time": prep_time,
        "cook_time": cook_time, "servings": servings, "ingredients": ingredients,
        "instructions": instructions, "notes": notes, "tags": tags,
        "source_url": source_url,
    })
    return RedirectResponse(f"/recipe/{rid}", status_code=303)


@router.post("/recipe/{rid}/delete")
def delete(request: Request, rid: int):
    """Delete a recipe (the browser asks for confirmation first)."""
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    repository.delete_recipe(rid)
    return RedirectResponse("/", status_code=303)
