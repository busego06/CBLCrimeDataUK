//
//  main.cpp
//  Crime Grouper
//
//  Created by Baranov Vladimir on 19/05/2026.
//

#include <iostream>
#include <string>
#include <filesystem>
#include <vector>
#include <fstream>

#include <random>

#include <sstream>

#include <cmath>

struct crime {
    double lat;
    double lon;
    //std::string type;
    int year;
    int month;
    std::string LSOA;
};

struct triple {
    int a;
    int b;
    int c;
};

struct probeResults {
    double newLatAvg;
    double newLonAvg;
    double additionCost;
    int id;
};

struct LSOA {
    double lat;
    double lon;
    std::string code;
    int cC;
};

struct coordinate {
    double lat;
    double lon;
};

struct weightedCoordinate {
    double lat;
    double lon;
    double weight;
};

struct gradient {
    double a;
    double b;
    double c;
    double d;
};

std::string corePath = "/Users/rookieruki/Documents/Crime\ Grouper/Crime\ Grouper/dataShort/";
std::vector<crime> allCrimes;

void ParseFiles(std::string coreDir) {
    std::vector<std::string> dataPieces;
    for (auto& dataDir : std::filesystem::directory_iterator(coreDir)) {
        std::string subDir = dataDir.path().generic_string();
        
        std::filesystem::path path(subDir);
        
        if(std::filesystem::is_directory(path)){
            for(auto& dataFile : std::filesystem::directory_iterator(subDir)){
                dataPieces.push_back(dataFile.path().generic_string());
            }
        }
        
        
        //dataPieces.push_back(dataDir.path().generic_string());
        
        std::cout<<dataDir<<std::endl;
    }
    std::cout << "Found " << dataPieces.size() << " data files." << std::endl;
    for (std::string filename : dataPieces) {
        
        std::ifstream test(filename);
        std::string buffer;
        int lines = 0;
        while (std::getline(test, buffer)) {
            std::stringstream buffStr(buffer);
            std::string bu;
            char del = ',';
            int i = 0;
            std::string time;
            double lat = 0;
            double lon = 0;
            //std::string type; TYPE IGNORED FOR TIME BEING
            int year;
            int month;
            bool success = true;
            
            
            std::string LSOA;
            
            while (std::getline(buffStr, bu, del) && success && lines > 0) {
                if (!bu.empty()) {
                    if (i == 1) {
                        time = bu;
                    }
                    else if (i == 4) {
                        lon = std::stod(bu);
                    }
                    else if (i == 5) {
                        lat = std::stod(bu);
                    }
                    //else if (i == 9) {
                    //    type = bu; TYPE IGNORED FOR TIME BEING
                    //}
                    else if (i == 7) {
                        LSOA = bu;
                    }
                }
                else {
                    //if (i == 4 || i == 5 || i == 9) {
                    if (i == 4 || i == 5 || i == 7) {
                        success = false;
                    }
                }
                i++;
            }
            if (success && lines > 0) {
                std::stringstream dateBuf(time);
                std::getline(dateBuf, bu, '-');
                year = std::stod(bu);
                std::getline(dateBuf, bu, '-');
                month = std::stod(bu);
                crime bufferCrime;
                bufferCrime.lat = lat;
                bufferCrime.lon = lon;
                bufferCrime.year = year;
                bufferCrime.month = month;
                bufferCrime.LSOA = LSOA;
                //bufferCrime.type = type; TYPE IGNORED FOR TIME BEING
                allCrimes.push_back(bufferCrime);
            }
            lines++;
        }
    }
    std::cout << "Finished parsing files. Total crime count: " << allCrimes.size() << std::endl;
    return;
}

int randomIntRange(int a, int b){
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<>distr(a,b);
    return distr(gen);
}

// Arrays start at 0 and go up to n-1
int findBound(double* array, int start, int length, double target){
    if(length==1){
        return start+1;
    } else if(length==0){
        return start;
    }
    double* middle = array + start + (length/2);
    //std::cout<<"Middle is "<<*middle<<"; length is "<<length<<"; halflength is "<<length/2<<std::endl;
    if(target >= *middle){
        return findBound(array, start + (length/2), length-length/2, target);
    } else {
        return findBound(array, start, length-length/2, target);
    }
}

triple segment(double* array, int start, int length, double low, double high){
    triple result = {0,0,0};
    result.a = findBound(array, start, length, low) - start;
    result.b = findBound(array, start, length, high) - result.a - start;
    result.c = length - result.a - result.b;
    return result;
}

void addValueSimple(double* array, int totalLength, int start, int length, double value){
    // Find how many values within own set exist that are smaller than new value
    int below = findBound(array, start, length, value);
    //std::cout<<below<<std::endl;
    // Find where new value will be located
    double* position = array + below;
    // Copy the chunk of memeory one size of double to the right to allow for insertion
    double* buffer = (double*)malloc(sizeof(double)*(totalLength-below-1));
    memcpy(buffer, position, (totalLength-below-1) * sizeof(double));
    memcpy(position+1, buffer, (totalLength-below-1) * sizeof(double));
    free(buffer);
    // Put the value in
    *position = value;
    // We are done
    return;
}

void addValue(double* arrayLats, double* arrayLons, int totalLength, std::vector<int>* starts, std::vector<int>* lengths, double lat, double lon, int targetArea){
    addValueSimple(arrayLats, totalLength, (*starts)[targetArea], (*lengths)[targetArea], lat);
    addValueSimple(arrayLons, totalLength, (*starts)[targetArea], (*lengths)[targetArea], lon);
    (*lengths)[targetArea]++;
    for(int i=targetArea+1; i<(*starts).size(); i++){
        (*starts)[i]++;
    }
}

// Returns the cost of adding a new lat/long coordinate to a set with given range in the arrays
probeResults probeAddition(double* arrayLats, double* arrayLons, int totalLength, int start, int length, double lat, double lon, double latAvg, double lonAvg){
    // Start by finding new average coordinates
    double newLatAvg = ((latAvg * length) + lat)/(length+1);
    double newLonAvg = ((lonAvg * length) + lon)/(length+1);
    
    // Define latitude flip range and direction the lat shifts
    double latLow = std::min(newLatAvg, latAvg);
    double latHigh = std::max(newLatAvg, latAvg);
    bool latDir = newLatAvg > latAvg;
    
    // Segment the latitude sub-array to find shift types
    triple latShift = segment(arrayLats, start, length, latLow, latHigh);
    // If lat shift is positive inverse the values
    if(latDir){
        int buf = latShift.c;
        latShift.c = latShift.a;
        latShift.a = buf;
    }
    
    // Calculate total latitude cost
    // Start by doing the obvious calculations
    double latCost = (latHigh-latLow) * (latShift.c - latShift.a);
    // Iterate through all values in greyzone and add their costs
    for(int i=0; i<latShift.b; i++){
        int index = latShift.a + i;
        latCost += abs(arrayLats[index]-newLatAvg)-abs(arrayLats[index]-latAvg);
    }
    
    // REPEAT FOR LON

    // Define longitude flip range and direction the lat shifts
    double lonLow = std::min(newLonAvg, lonAvg);
    double lonHigh = std::max(newLonAvg, lonAvg);
    bool lonDir = newLonAvg > lonAvg;
    
    // Segment the longitude sub-array to find shift types
    triple lonShift = segment(arrayLons, start, length, lonLow, lonHigh);
    // If lon shift is positive inverse the values
    if(lonDir){
        int buf = lonShift.c;
        lonShift.c = lonShift.a;
        lonShift.a = buf;
    }
    
    // Calculate total longitude cost
    // Start by doing the obvious calculations
    double lonCost = (lonHigh-lonLow) * (lonShift.c - lonShift.a);
    // Iterate through all values in greyzone and add their costs
    for(int i=0; i<lonShift.b; i++){
        int index = lonShift.a + i;
        lonCost += abs(arrayLons[index]-newLonAvg)-abs(arrayLons[index]-lonAvg);
    }
    
    // Calculate final cost
    double finalCost = (latCost + lonCost) / sqrt(length + 1);
    
    return probeResults(newLatAvg, newLonAvg, finalCost);
}

// Find the id of the area with lowest average cost of adding a new element
probeResults findBestFitArea(double* arrayLats, double* arrayLons, int totalLength, std::vector<int>* starts, std::vector<int>* lengths, double lat, double lon, std::vector<double>* latAverages, std::vector<double>* lonAverages){
    probeResults best(0,0,10000000000,0);
    for(int i=0; i<(*starts).size(); i++){
        probeResults areaCost = probeAddition(arrayLats, arrayLons, totalLength, (*starts)[i], (*lengths)[i], lat, lon, (*latAverages)[i], (*lonAverages)[i]);
        //std::cout<<"Cost "<<i<<": "<<areaCost.additionCost<<" , starts at "<<(*starts)[i]<<" with length "<<(*lengths)[i]<<std::endl;
        if(areaCost.additionCost < best.additionCost){
            best = areaCost;
            best.id = i;
        }
    }
    return best;
}


/*
 Helper function for findint the ID of an LSOA by code in an LSOA vector
 */
int findByCode(std::vector<LSOA>* LSOAs, std::string code){
    int i = 0;
    // Cycle through every entry in LSOA vector
    for(LSOA check : (*LSOAs)){
        // Compare code
        if(check.code == code){
            // Return if found
            return i;
        } else {
            i++;
        }
    }
    // Return -1 if not found
    return -1;
}


/*
 Infers LSOA coordinates from weighted averages of the coordinates of all crimes that happened within the LSOA.
 Getting data like this may help with accounting for LSOAs in sparsely populated regions where most of the population of the LSOA
 may be on just one side of it, causing the average crime area to be in different space than the geographical mean
 */
std::vector<LSOA> getLSOACoordinates(std::vector<crime>* crimes){
    
    int i = 0;
    // Initialize LSOA vector
    std::vector<LSOA> LSOAs;
    // Iterate through every crime
    for(crime bufferCrime : (*crimes)){
        
        if(i%1000 == 0){
            std::cout<<i<<std::endl;
        }
        i++;
        // Check the index of the LSOA in the vector
        std::string crimeLSOA = bufferCrime.LSOA;
        int id = findByCode(&LSOAs, crimeLSOA);
        if(id == -1){
            // If not in vector, add to vector
            LSOAs.push_back(LSOA{bufferCrime.lat, bufferCrime.lon, crimeLSOA, 1});
        } else {
            // If in vector add all the values
            LSOAs[id].lat += bufferCrime.lat;
            LSOAs[id].lon += bufferCrime.lon;
            LSOAs[id].cC++;
        }
    }
    // Cycle through every LSOA
    for(int i=0; i<LSOAs.size(); i++){
        // Divide to convert the totals into averages
        LSOAs[i].lat /= (double)LSOAs[i].cC;
        LSOAs[i].lon /= (double)LSOAs[i].cC;
    }
    // return the results
    return LSOAs;
}

/*
 Function to load all of the essential inputs from an input file
 Loads:
    1. Path to data directory ( for crimes ) !!! CANNOT DEAL WITH DIRECTORY IN "" OR WITH SPACES FOR THE TIME BEING !!!
    2. Amount of center points to start with; lets call it x
    3. x center point coordinates, one set of coordinates per line
    4. Amount of center LSOAs to start with; lets call it y
    5. y LSOA codes, one LSOA code per line
 
    Writes directly to, using pointers:
        string storing path to data directory
        vector containing center points used for the initialization
 */

void loadInputs(std::vector<std::vector<LSOA>>* groupLSOAVectors,
                std::vector<coordinate>* centers,
                std::vector<double>* SqD,
                std::vector<double>* totalWeights){
    
    // Open input file, declare buffer and delimenator (uses , as by the csv norms)
    std::ifstream inFile("input.csv");
    std::string buffer;
    char del = ',';
    int line = 0;
    
    while (std::getline(inFile, buffer)) {
        
        
        std::stringstream buffStr(buffer);
        std::string bu;
        bool success = true;
        
        double lat = 0;
        double lon = 0;
        double weight = 0;
        
        int i = 0;
        
        while (std::getline(buffStr, bu, del) && success) {
            if (!bu.empty()) {
                
                
                if (i == 0) {
                    lat = std::stod(bu);
                }
                else if (i == 1) {
                    lon = std::stod(bu);
                }
                else if (i == 2) {
                    weight = std::stod(bu);
                }
                
            }
            i++;
        }
        if (success) {
            (*groupLSOAVectors).push_back(std::vector<LSOA>{LSOA{lat, lon, "FAKE", (int)weight}});
            (*centers).push_back(coordinate{lat,lon});
            (*SqD).push_back(0);
            (*totalWeights).push_back(weight);
        }
        
    }
    
    // UNFINISHED
}

/*
 Function that defines the influence of crime count
 Currently linear
 */
double weightingFunction(int crimeCount){
    return (double)crimeCount;
}

/*
 Function that returns the result of lat partial derivative / lat gradient of the squared distance function for a group of LSOAs and its center
 */


coordinate getGradient(double lat, double lon, std::vector<LSOA>* coordinatesLSOA){
    // We begin by constructing the effective function for the total squared distance
    // It will be of the form a*x^2 + b*x + c
    coordinate gradient = {0,0};
    for (LSOA buf : (*coordinatesLSOA)){
        //std::cout<<buf.lat<<" "<<buf.lon<<" "<<buf.code<<" "<<buf.cC<<std::endl;
        double coef_ = (2 * std::sqrt(pow(lat-buf.lat,2)+pow(lon-buf.lon,2)));
        if(coef_ < 0.0000000001){
            coef_ = 0;
        } else {
            coef_ = weightingFunction(buf.cC) / coef_;
        }
        gradient.lat += coef_ * (2*lat - 2*buf.lat);
        gradient.lon += coef_ * (2*lon - 2*buf.lon);
        //std::cout<<coef_<<std::endl;
    }
    return gradient;
}

/*
 Step function
 */
double stepFunction(int step, double q = 0.00001, int maxstep = 100){
    return (std::sqrt(maxstep-step) * q);
}

/*
 Normalizes the gradient
 */
coordinate normalizeGradient(coordinate gradient){
    double length = std::sqrt(pow(gradient.lat, 2) + pow(gradient.lon, 2));
    return coordinate{gradient.lat / length, gradient.lon / length};
}

/*
 Function that optimizes the center point for a given set of coordinates
 */
coordinate gradientDescent(double lat, double lon, std::vector<LSOA>* coordinates, int steps){
    double stepSize = 0.000001;
    double currLat = lat;
    double currLon = lon;
    for(int i=0; i<steps; i++){
        coordinate gradient = getGradient(currLat, currLon, coordinates);
        currLat -= stepFunction(i, stepSize) * gradient.lat;
        currLon -= stepFunction(i, stepSize) * gradient.lon;
    }
    return coordinate{currLat, currLon};
}

double lognofx(double n, double x){
    return std::log(x) / std::log(n);
}

coordinate gradientDescentHalfDecay(double lat, double lon, double newLat, double newLon, std::vector<LSOA>* coordinates, double totalWeight, double newWeight){
    double targetPrecision = 0.00001; // very very small distance
    double currLat = lat;
    double currLon = lon;
    double estShift = std::sqrt(pow(newLat-lat,2)+pow(newLon-lon,2)) * newWeight / (totalWeight+newWeight);
    double currStep = estShift / 1.5;
    int steps = std::ceil(lognofx(1.5, currStep / targetPrecision));
    //std::cout<<"Half decay steps: "<<steps<<std::endl;
    for(int i = 0; i<steps; i++){
        coordinate gradient = getGradient(lat, lon, coordinates);
        coordinate normalGradient = normalizeGradient(gradient);
        currLat -= currStep * normalGradient.lat;
        currLon -= currStep * normalGradient.lon;
        currStep /= 1.5;
    }
    return coordinate(currLat, currLon);
}

/*
 Function that finds the total weighted squared distance for a set of points
 */
double getTotalDistance(double lat, double lon, std::vector<LSOA>* coordinatesLSOA){
    double tWSqD = 0;
    for (LSOA buf : (*coordinatesLSOA)){
        //std::cout<<"Lat debug " <<buf.lat<<" "<<lat<<" "<<buf.lon<<" "<<lon<<" "<<weightingFunction(buf.cC)<<std::endl;
        double val = (pow((buf.lat - lat),2) + pow((buf.lon - lon),2));
        tWSqD += std::sqrt(val) * weightingFunction(buf.cC);
    }
    return tWSqD;
}

/*
 Function to attempt addition of value to group, probing the total squared distance increase and new center point
 */
weightedCoordinate probeSqd(double lat, double lon, std::vector<LSOA>* LSOAs, LSOA newLSOA){
    double currentSqd = getTotalDistance(lat, lon, LSOAs);
    //std::cout<<"Current: "<<currentSqd<<std::endl;
    (*LSOAs).push_back(newLSOA);
    coordinate newCenter = gradientDescent(lat, lon, LSOAs, 40);
    double SqdCost = getTotalDistance(newCenter.lat, newCenter.lon, LSOAs) - currentSqd;
    //std::cout<<SqdCost<<std::endl;
    (*LSOAs).pop_back();
    return weightedCoordinate {newCenter.lat, newCenter.lon, SqdCost};
}

/*
 Function to attempt addition of value to group, probing the total squared distance increase and new center point
 */
weightedCoordinate probeSqdHalfDecay(double lat, double lon, std::vector<LSOA>* LSOAs, double sqd,  double totalWeight, LSOA newLSOA){
    double currentSqd = sqd;
    //std::cout<<"Current: "<<currentSqd<<std::endl;
    (*LSOAs).push_back(newLSOA);
    coordinate newCenter = gradientDescentHalfDecay(lat, lon, newLSOA.lat, newLSOA.lon, LSOAs, totalWeight, newLSOA.cC);
    double SqdCost = getTotalDistance(newCenter.lat, newCenter.lon, LSOAs) - currentSqd;
    std::cout<<SqdCost<<"   "<<currentSqd<<std::endl;
    (*LSOAs).pop_back();
    return weightedCoordinate {newCenter.lat, newCenter.lon, SqdCost};
}

/*
 Function to probe sqd of every group and add to best fit group
 */
void distributeToBestSqdFit(std::vector<std::vector<LSOA>>* groups, std::vector<coordinate>* centers, std::vector<double>* totalWeights, std::vector<double>* SQDs,  LSOA newLSOA){
    int i = 0;
    weightedCoordinate bestFit = {0,0,1000000000.0};
    int best = 0;
    for(coordinate center : (*centers)){
        //std::cout<<"Trying to match "<<center.lat<<" "<<center.lon<<std::endl;
        //weightedCoordinate matchOld = probeSqd(center.lat, center.lon, &((*groups)[i]), newLSOA);
        
        weightedCoordinate match = probeSqdHalfDecay(center.lat, center.lon, &((*groups)[i]), (*totalWeights)[i], (*SQDs)[i], newLSOA);
        
        //std::cout<<"Sqd normal: "<<match.weight<<"     Sqd half decay: "<<halfDecayMatch.weight<<std::endl;
        
        
        //std::cout<<"Match cost: "<<match.weight<<std::endl;
        if(match.weight < bestFit.weight){
            bestFit = match;
            best = i;
        }
        i++;
    }
    //std::cout<<"Matched! "<<best<<" at cost "<<bestFit.weight<<std::endl;
    (*centers)[best] = coordinate {bestFit.lat, bestFit.lon};
    (*groups)[best].push_back(newLSOA);
    (*totalWeights)[best] += newLSOA.cC;
    (*SQDs)[best] += bestFit.weight;
    return;
}

/*
 Function that saves pre-calulated LSOAs to a file because LSOA pre-calculation takes very long
 */
void saveLSOAs(std::vector<LSOA>* LSOAs, std::string file){
    std::ofstream LSOAfile(file);
    for(LSOA bufLSOA : (*LSOAs)){
        LSOAfile<<bufLSOA.lat<<","<<bufLSOA.lon<<","<<bufLSOA.code<<","<<bufLSOA.cC<<std::endl;
    }
}

/*
 Loading pre-calculated LSOAs
 Expects to get a pointer to an empty LSOA vector
 */
bool loadLSOAs(std::vector<LSOA>* LSOAs, std::string file){
    
    
    std::filesystem::path path(file);
    if(!std::filesystem::exists(path)){
        return false;
    }
    
    
    std::ifstream LSOAfile(file);
    std::string buffer;
    int lines = 0;
    while (std::getline(LSOAfile, buffer)) {
        std::stringstream buffStr(buffer);
        std::string bu;
        char del = ',';
        
        std::string code;
        double lat = 0;
        double lon = 0;
        int cC = 0;
        //std::string type; TYPE IGNORED FOR TIME BEING
        
        int i = 0;
        while (std::getline(buffStr, bu, del)) {
            if(i==0){
                lat = std::stod(bu);
            } else if(i==1){
                lon = std::stod(bu);
            } else if(i==2){
                code = bu;
            } else if(i==3){
                cC = std::stoi(bu);
            }
            i++;
        }
        (*LSOAs).push_back(LSOA{lat,lon,code,cC});

    }
    
    return true;
}

int zones = 2;

int main(int argc, const char * argv[]) {
    
    
    
    std::vector<LSOA> LSOAs;
    
    if(!loadLSOAs(&LSOAs, "LSOAs.csv")){
        std::cout<<"LSOA preloaded data not found, this run of the code will preload LSOAs into a file and return"<<std::endl;
        ParseFiles(corePath);
        std::cout<<"Beginning LSOA average coordinate calculations"<<std::endl;
        LSOAs = getLSOACoordinates(&allCrimes);
        std::cout<<"Finished calculating LSOA positions, writing..."<<std::endl;
        saveLSOAs(&LSOAs, "LSOAs.csv");
        std::cout<<"Done. Returning."<<std::endl;
        return 0;
    } else {
        std::cout<<"Loaded "<<LSOAs.size()<<" LSOAs from file"<<std::endl;
    }
    
    
    
    
    
    
    
    
    
    /*
    //Allocate memory for lat/long arrays of arrays         >>> OLD CODE, PER CRIME BASIS <<<
    double* latArray = (double*)malloc(sizeof(double)*allCrimes.size());    >>> OLD CODE, PER CRIME BASIS <<<
    double* lonArray = (double*)malloc(sizeof(double)*allCrimes.size());    >>> OLD CODE, PER CRIME BASIS <<<
     */
    
    /*
    
    // Allocate memory for lat/long arrays
    double* latArray = (double*)malloc(sizeof(double)*allCrimes.size());
    double* lonArray = (double*)malloc(sizeof(double)*allCrimes.size());
    
    // Allocate vector pointers
    std::vector<int>* starts = (std::vector<int>*)malloc(sizeof(std::vector<int>));
    std::vector<int>* lengths = (std::vector<int>*)malloc(sizeof(std::vector<int>));
    std::vector<double>* latAverages = (std::vector<double>*)malloc(sizeof(std::vector<double>));
    std::vector<double>* lonAverages = (std::vector<double>*)malloc(sizeof(std::vector<double>));
    
    //Initialize vectors
    (*starts) = std::vector<int>(zones, 0);
    (*lengths) = std::vector<int>(zones, 0);
    (*latAverages) = std::vector<double>(zones, 0);
    (*lonAverages) = std::vector<double>(zones, 0);
     
     */
    
    std::vector<std::vector<LSOA>> groupLSOAVectors;
    std::vector<coordinate> centers;
    std::vector<double> SqD;
    std::vector<double> totalWeights;
    
    
    for(int i=0; i<zones; i++){
        groupLSOAVectors.push_back(std::vector<LSOA>());
        centers.push_back(coordinate{0,0});
        SqD.push_back(0);
        totalWeights.push_back(0.0);
    }
    
    centers[0] = {-0.174801, 51.485605};
    centers[1] = {-2.699038, 53.420582};
    
    groupLSOAVectors[0].push_back({-0.174801, 51.485605, "1", 1000});
    groupLSOAVectors[1].push_back({-2.699038, 53.420582, "1", 1000});
    
    totalWeights[0] = 1000;
    totalWeights[1] = 1000;
    
    int randomSamples = (int)LSOAs.size() / 10;
    
    std::cout<<"Begun random sample distribution!"<<std::endl;
    
    for(int i=0; i<randomSamples; i++){
        int id = randomIntRange(0, (int)LSOAs.size());

        LSOA bufLSOA = LSOAs[id];
        LSOAs.erase(std::next(LSOAs.begin(),id));
        
        // PUT LSOA IN GROUP
        //std::cout<<"Starting distribution"<<std::endl;
        distributeToBestSqdFit(&groupLSOAVectors, &centers, &totalWeights, &SqD, bufLSOA);
        std::cout<<"Distributed"<<std::endl;
        //
    }
    std::cout<<"Random samples distributed!"<<std::endl;
    
    int i = 0;
    for(LSOA bufLSOA : LSOAs){
        // PUT LSOA IN GROUP
        distributeToBestSqdFit(&groupLSOAVectors, &centers, &totalWeights, &SqD, bufLSOA);
        std::cout<<"Distributed "<<i<<std::endl;
        i++;
    }
    

    /*
    
    for(int i=0; i<LSOAs.size(); i++){
        int id = randomIntRange(0, LSOAs.size()-i);
        crime entry = allCrimes[id];
        allCrimes.erase(std::next(allCrimes.begin(),id));
        if(i%1000 == 0){
            std::cout<<"Randomly grabbed id "<<id<<" out of "<<allCrimes.size()-i<<" available."<<std::endl;
        }
        double lat = entry.lat;
        double lon = entry.lon;
        
        probeResults bestFit = findBestFitArea(latArray, lonArray, total, starts, lengths, lat, lon, latAverages, lonAverages);
        std::cout<<"Value of "<<lat<<":"<<lon<<" best fit into "<<bestFit.id<<" at cost "<<bestFit.additionCost<<std::endl;
        addValue(latArray, lonArray, total, starts, lengths, lat, lon, bestFit.id);
        (*latAverages)[bestFit.id] = bestFit.newLatAvg;
        (*lonAverages)[bestFit.id] = bestFit.newLonAvg;
        
        
    }
    
    for(int i=0; i<zones; i++){
        std::cout<<(*latAverages)[i]<<" "<<(*lonAverages)[i]<<std::endl;
    }
    
    double testArray[9] = {1.0,2.0,3.0,4.0,1.5,2.5,3.5,4.5,0.0};
    
    //std::cout<<findBound(testArray, 0, 5, 0.2)<<std::endl;
    addValueSimple(testArray, 9, 0, 4, 4.2);
    triple tess = segment(testArray, 0, 5, 1.9, 3.9);
    std::cout<<tess.a<<" "<<tess.b<<" "<<tess.c<<std::endl;
    
    for(double value : testArray){
        std::cout<<value<<" ";
    }
    std::cout<<std::endl;
    */
    
    
    
    // insert code here...
    return EXIT_SUCCESS;
}
