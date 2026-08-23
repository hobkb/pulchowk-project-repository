from django.core.paginator import EmptyPage, Paginator
from rest_framework.response import Response
from rest_framework import status


def success_response(
    *,
    data=None,
    message="Success",
    status=status.HTTP_200_OK,
    extra=None,
):
    """
    Returns a standardized success response.

    `extra` merges additional top-level keys into the envelope (used by
    `paginated_response` for the `pagination` block) without disturbing the
    `success` / `message` / `data` shape every client already reads.
    """

    body = {
        "success": True,
        "message": message,
        "data": data,
    }
    if extra:
        body.update(extra)

    return Response(body, status=status)


# Page sizes are per-endpoint because the shapes differ: a card grid wants a
# number that divides evenly into 2, 3 and 4 columns, while a queue of rows
# reads better longer. These are the ceilings a client may request.
DEFAULT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 100


def paginated_response(
    request,
    queryset,
    serialize,
    *,
    page_size=DEFAULT_PAGE_SIZE,
    max_page_size=MAX_PAGE_SIZE,
    message="Success",
):
    """
    Pages a queryset and returns it in the standard envelope.

    `data` stays a plain list, so a client that ignores paging still gets a
    usable first page rather than an object it cannot iterate. The counts a
    UI needs to draw controls live alongside it under `pagination`.

    `serialize` receives the page's object list and returns the serialized
    rows, letting each view keep its own serializer and context.
    """
    try:
        requested_size = int(request.query_params.get("page_size", page_size))
    except (TypeError, ValueError):
        requested_size = page_size
    size = max(1, min(requested_size, max_page_size))

    paginator = Paginator(queryset, size)

    try:
        number = int(request.query_params.get("page", 1))
    except (TypeError, ValueError):
        number = 1

    # A page number past the end returns the last page rather than a 404:
    # it is reachable simply by deleting rows while someone is reading, and
    # an error there would be a worse answer than the nearest real page.
    try:
        page = paginator.page(max(1, number))
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return success_response(
        data=serialize(page.object_list),
        message=message,
        extra={
            "pagination": {
                "page": page.number,
                "page_size": size,
                "total_count": paginator.count,
                "total_pages": paginator.num_pages,
                "has_next": page.has_next(),
                "has_previous": page.has_previous(),
            }
        },
    )
