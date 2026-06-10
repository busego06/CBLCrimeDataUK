from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

# Create your views here.
def clusterDashboard(request):
    return HttpResponse(loader.get_template("./test.html").render())