from django.urls import path
from . import views

urlpatterns = [
    path("predictionDashboard/", views.predictionDashboard, name="predictionDashboard"),
]