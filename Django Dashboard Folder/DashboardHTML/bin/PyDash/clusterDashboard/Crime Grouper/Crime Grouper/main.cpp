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

// Set the proportion for lat/lon scaling to account for difference in degree importance
const double LON_SCALE = std::cos(54.0 * std::acos(-1.0) / 180.0);

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

std::string corePath = "data/";
std::vector<crime> allCrimes;

const double PI = std::acos(-1.0);

double r(double deg){
    return deg * PI / 180;
}

// Proportional distance in lat/long space, not in KM
double distanceHaversine(double lat1, double lon1, double lat2, double lon2){
    lat1 = r(lat1); lon1 = r(lon1 / LON_SCALE); lat2 = r(lat2); lon2 = r(lon2 / LON_SCALE);
    double dLat = lat2-lat1;
    double dLon = lon2-lon1;
    double sinHalfDLat = std::sin(dLat/2);
    double sinHalfDLon = std::sin(dLon/2);
    double a = sinHalfDLat * sinHalfDLat + std::cos(lat1) * std::cos(lat2) * sinHalfDLon * sinHalfDLon;
    return a;
}

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
        std::cout<<"Reading "<<filename<<std::endl;
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
                        std::cout<<bu<<std::endl;
                        lon = std::stod(bu);
                    }
                    else if (i == 5) {
                        std::cout<<bu<<std::endl;
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
                std::cout<<bu<<std::endl;
                year = std::stod(bu);
                std::getline(dateBuf, bu, '-');
                std::cout<<bu<<std::endl;
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
                std::vector<double>* totalWeights,
                std::string iFile){
    
    // Open input file, declare buffer and delimenator (uses , as by the csv norms)
    std::ifstream inFile(iFile);
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
            if (!bu.empty() && !(bu == " ")) {
                
                
                if (i == 0) {
                    std::cout<<bu<<std::endl;
                    lat = std::stod(bu);
                }
                else if (i == 1) {
                    std::cout<<bu<<std::endl;
                    lon = std::stod(bu);
                }
                else if (i == 2) {
                    std::cout<<bu<<std::endl;
                    weight = std::stod(bu);
                }
                
            } else {
                success = false;
            }
            i++;
        }
        // Apply scaling factor
        lon *= LON_SCALE;
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
        coordinate gradient = getGradient(currLat, currLon, coordinates);
        coordinate normalGradient = normalizeGradient(gradient);
        currLat -= currStep * normalGradient.lat;
        currLon -= currStep * normalGradient.lon;
        currStep /= 1.5;
    }
    return coordinate{currLat, currLon};
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
    //std::cout<<SqdCost<<"   "<<currentSqd<<std::endl;
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
        
        weightedCoordinate match = probeSqdHalfDecay(center.lat, center.lon, &((*groups)[i]), (*SQDs)[i], (*totalWeights)[i],  newLSOA);
        
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
                std::cout<<bu<<std::endl;
                lat = std::stod(bu);
            } else if(i==1){
                std::cout<<bu<<std::endl;
                lon = std::stod(bu);
            } else if(i==2){
                code = bu;
            } else if(i==3){
                std::cout<<bu<<std::endl;
                cC = std::stoi(bu);
            }
            i++;
        }
        // Applies scaling factor on pushback for distance calculations
        (*LSOAs).push_back(LSOA{lat,lon*LON_SCALE,code,cC});

    }
    
    return true;
}

void saveLSOAGroups(std::vector<std::vector<LSOA>> *LSOAs, std::string oFile){
    std::ofstream outFile(oFile);
    int i = 0;
    for(std::vector<LSOA> group : (*LSOAs)){
        for(LSOA lsoa : group){
            outFile<<lsoa.code<<","<<lsoa.lat<<","<<(lsoa.lon/LON_SCALE)<<","<<i<<std::endl;
        }
        i++;
    }
    outFile.close();
}

void saveLSOAGroupsReassign(std::vector<std::vector<LSOA>> *LSOAs, std::vector<coordinate>* centers, std::string oFile){
    std::ofstream outFile(oFile);
    for(std::vector<LSOA> group : (*LSOAs)){
        for(LSOA lsoa : group){
            double optDist = 999999999;
            int optID = 0;
            int i = 0;
            for(coordinate center : (*centers)){
                double hDist = distanceHaversine(center.lat, center.lon, lsoa.lat, lsoa.lon);
                if(hDist < optDist){
                    optDist = hDist;
                    optID = i;
                }
                i++;
            }
            outFile<<lsoa.code<<","<<lsoa.lat<<","<<(lsoa.lon/LON_SCALE)<<","<<optID<<std::endl;
        }
    }
    int i = 0;
    for(coordinate center : (*centers)){
        outFile<<"CENTER"<<","<<center.lat<<","<<center.lon/LON_SCALE<<","<<i<<std::endl;
        i++;
    }
    
    outFile.close();
}


int main(int argc, const char * argv[]) {
    
    std::string inFile = "input.csv";
    std::string outFile = "output.csv";
    std::string lsoaPath = "LSOAs.csv";
    
    if(argc != 4){
        std::cout<<"Wrong input count, using defaults!"<<std::endl;
    } else {
        inFile = argv[1];
        outFile = argv[2];
        lsoaPath = argv[3];
    }
    
    std::vector<LSOA> LSOAs;
    
    if(!loadLSOAs(&LSOAs, lsoaPath)){
        std::cout<<"LSOA preloaded data not found, this run of the code will preload LSOAs into a file and return"<<std::endl;
        ParseFiles(corePath);
        std::cout<<"Beginning LSOA average coordinate calculations"<<std::endl;
        LSOAs = getLSOACoordinates(&allCrimes);
        std::cout<<"Finished calculating LSOA positions, writing..."<<std::endl;
        saveLSOAs(&LSOAs, lsoaPath);
        std::cout<<"Done. Returning."<<std::endl;
        return 0;
    } else {
        std::cout<<"Loaded "<<LSOAs.size()<<" LSOAs from file"<<std::endl;
    }
 
    std::vector<std::vector<LSOA>> groupLSOAVectors;
    std::vector<coordinate> centers;
    std::vector<double> SqD;
    std::vector<double> totalWeights;
    
    loadInputs(&groupLSOAVectors, &centers, &SqD, &totalWeights, inFile);

    
    int randomSamples = (int)LSOAs.size() / 10;
    
    std::cout<<"Begun random sample distribution!"<<std::endl;
    
    for(int i=0; i<randomSamples; i++){
        int id = randomIntRange(0, (int)LSOAs.size()-1);

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
    
    //saveLSOAGroupsRe(&groupLSOAVectors, outFile);
    saveLSOAGroupsReassign(&groupLSOAVectors, &centers, outFile);
    
    return EXIT_SUCCESS;
}
