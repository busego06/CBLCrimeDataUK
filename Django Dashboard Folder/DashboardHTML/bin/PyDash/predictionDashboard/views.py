from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

# Create your views here.
def predictionDashboard(request):
    return HttpResponse(loader.get_template("./predictionModel.html").render())