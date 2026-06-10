from django.urls import path
from . import views

urlpatterns = [
    path("clusterDashboard/", views.clusterDashboard, name="clusterDashboard"),
]