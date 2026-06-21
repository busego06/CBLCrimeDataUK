from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.conf import settings

from django.views.decorators.csrf import ensure_csrf_cookie

# Libraries for C++ call implementation
import os, subprocess, json, tempfile, shutil

GROUPING_DIR = settings.BASE_DIR / "clusterDashboard" / "Crime Grouper" / "Crime Grouper"
EXECUTABLE = GROUPING_DIR / "build" / "Clustering"
if(os.name == "nt"):
    EXECUTABLE = GROUPING_DIR / "build" / "Clustering.exe"
LSOA_CACHE = GROUPING_DIR / "LSOAs.csv"

def runClustering(request):
    if request.method != "POST":
        return JsonResponse({"error": "Wrong method"}, status = 405)
    
    try:
        # Attempt to load center starting points from the body of the request
        centersJson = json.loads(request.body)
    except:
        # Parsing failed
        return JsonResponse({"error": "JSON Error"}, status=400)
    
    # Check that the list with centers even exists
    if not(type(centersJson) == list and centersJson):
        return JsonResponse({"error": "Bad input"}, status=400)

    # Check existance of all numeric fields
    for center in centersJson:
        # Cycle through the numeric keys
        for key in ["lat","lon","weight"]:
            try:
                # Test if data can be extracted
                test = float(center[key])
            except:
                # Return an error if something fails, specify which field messed up
                return JsonResponse({"error":key+" field has invalid value"}, status=400)
        
    # Sanity check ranges for the fields, add values to a list
    stored = []

    for center in centersJson:

        # Extract values
        lat = float(center["lat"])
        lon = float(center["lon"])
        weight = float(center["weight"])

        # Label any invalidity
        invalid = False
        if(lat > 61 or lat < 49):
            invalid = "lat"
        elif(lon > 2 or lon < -9):
            invalid = "lon"
        elif(weight < 0):
            invalid = "weight"
        
        # Return an error if invalid
        if(invalid):
            return JsonResponse({"error":"Impossible value in "+invalid}, status=400)
        
        # If all passed add to storage
        stored.append((lat,lon,weight))
    
    # Make temporary directory for C++ IO
    tempDir = tempfile.mkdtemp()
    inputPath = os.path.join(tempDir, "input.csv")
    outputPath = os.path.join(tempDir, "output.csv")

    # Do some magic to join all data into a coherent csv text
    lines = "\n".join(f"{lat},{lon},{weight}" for lat, lon, weight in stored)

    # Write the lines to a file
    with open(inputPath, "w") as file:
        file.writelines(lines)

    # Some fancy stuff to run the C++ compiled executable
    try:
        res = subprocess.run(
            [str(EXECUTABLE), inputPath, outputPath, str(LSOA_CACHE)],
            cwd=GROUPING_DIR, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        # Clean up temp files
        shutil.rmtree(tempDir, ignore_errors=True)
        return JsonResponse({"error":"C++ timed out"}, status = 504)
    
    # Check if C++ had an error
    if(res.returncode != 0):
        # Clean up temp files
        shutil.rmtree(tempDir, ignore_errors=True)
        return JsonResponse({"error":"C++ clustering failed", "detail":res.stderr}, status = 500)
    
    # Read C++ output
    with open(outputPath) as file:
        resultLines = file.read().splitlines()

    LSOAs = []
    centers = []
    for line in resultLines:
        # Skip a cycle if line is empty
        if (not line):
            continue   

        # extract info
        lsoaCode, lat, lon, group = line.split(",")

        # If the LSOA ID is FAKE (fake center) skip a cycle
        if (lsoaCode == "FAKE"):
            continue

        if (lsoaCode == "CENTER"):
            centers.append({"lat":float(lat), "lon":float(lon), "group":int(group)})

        # Add a json entry
        LSOAs.append({"code":lsoaCode, "lat":float(lat), "lon":float(lon), "group":int(group)})

    # Clean up temp files
    shutil.rmtree(tempDir, ignore_errors=True)

    # Return a json to the JS script
    return JsonResponse({"LSOAs":LSOAs, "centers":centers})

@ensure_csrf_cookie
def clusterDashboard(request):
    return HttpResponse(loader.get_template("./clusters.html").render())