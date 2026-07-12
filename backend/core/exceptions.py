from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Formats all DRF exceptions into a consistent API response.
    """

    response = exception_handler(exc, context)

    if response is None:
        return response

    message = "Request failed."
    errors = None

    if isinstance(response.data, dict):

        if "detail" in response.data:
            message = response.data["detail"]

        else:
            message = "Validation failed."
            errors = response.data

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }

    return response