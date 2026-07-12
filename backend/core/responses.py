from rest_framework.response import Response
from rest_framework import status

def success_response(
    *,
    data=None,
    message="Success",
    status=status.HTTP_200_OK,
):
    """
    Returns a standardized success response.
    """

    return Response(
        {
            "success": True,
            "message": message,
            "data": data,
        },
        status=status,
    )