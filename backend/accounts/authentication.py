from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authenticate users using a JWT stored in the ``access`` cookie.

    This authentication backend behaves like SimpleJWT's default
    authentication, except it retrieves the access token from an HTTP
    cookie instead of the ``Authorization`` header.
    """

    def authenticate(self, request) -> tuple:
        
        token = request.COOKIES.get("access")

        if not token:
            return None

        validated_token = self.get_validated_token(token)
        user = self.get_user(validated_token)

        return (user, validated_token)