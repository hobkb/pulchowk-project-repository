from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from .models import Department
from .serializers import DepartmentSerializer

class DepartmentListView(ListAPIView):
    """
    Public endpoint to list all available departments.
    """
    queryset = Department.objects.all().select_related("campus")
    serializer_class = DepartmentSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
