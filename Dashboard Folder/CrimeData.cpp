#define _USE_MATH_DEFINES
#include <cmath>

#include <iostream>
#include <string>
#include <filesystem>
#include <vector>
#include <fstream>

#include <sstream>


#include <opencv2/core.hpp>
#include <opencv2/opencv.hpp>
#include "opencv2/highgui/highgui.hpp"

struct crime {
    double lat;
    double lon;
    std::string type;
    int year;
    int month;
};

struct mapEntry {
    double area;
    double density;
    std::vector<crime> crimes;
}; 

struct doubleTuple {
    double d1;
    double d2;
};

struct doubleQuad {
    double d1;
    double d2;
    double d3;
    double d4;
};

struct box {
    double minx;
    double miny;
    double maxx;
    double maxy;
};


std::string corePath = "./data/";
std::vector<crime> allCrimes;

std::vector<std::vector<crime>> allAllCrimes;

int finalWidth;
int finalHeight;

void ParseFiles(std::string coreDir) {

    std::vector<std::string> dataPieces;

    for (auto& dataDir : std::filesystem::directory_iterator(coreDir)) {
        std::string subDir = dataDir.path().generic_string();
        //for (auto& dataFile : std::filesystem::directory_iterator(subDir)) {
            //dataPieces.push_back(dataFile.path().generic_string());
        //}
        dataPieces.push_back(dataDir.path().generic_string());
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
            std::string type;
            int year;
            int month;

            bool success = true;

            while (std::getline(buffStr, bu, del) && success && lines > 0) {
                if (!bu.empty()) {
                    if (i == 1) {
                        time = bu;
                    }
                    else if (i == 4) {
                        lat = std::stod(bu);
                    }
                    else if (i == 5) {
                        lon = std::stod(bu);
                    }
                    else if (i == 9) {
                        type = bu;
                    }
                }
                else {
                    if (i == 4 || i == 5 || i == 9) {
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
                bufferCrime.type = type;
                allCrimes.push_back(bufferCrime);
            }

            lines++;
        }
    }
    std::cout << "Finished parsing files. Total crime count: " << allCrimes.size() << std::endl;
    return;
}


double dp(double in) {
    return std::log10(in);
}

box findEdges(std::vector<crime> crimeVector) {
    double lLon = 1000;
    double lLat = 1000;
    double hLon = 0;
    double hLat = 0;
    for (crime bufCrime : crimeVector) {
        if (bufCrime.lat < lLat) {
            lLat = bufCrime.lat;
        }
        if (bufCrime.lat > hLat) {
            hLat = bufCrime.lat;
        }
        if (bufCrime.lon < lLon) {
            lLon = bufCrime.lon;
        }
        if (bufCrime.lon > hLon) {
            hLon = bufCrime.lon;
        }
    }
    return box(lLon, lLat, hLon, hLat);
}

void initMap(std::vector<std::vector<mapEntry>>* map, doubleTuple latLim, double latUnit, double lonUnit) {
    for (int i = 0; i < finalWidth; i++) {
        for (int j = 0; j < finalHeight; j++) {
            double lowLat = latLim.d1 + i * latUnit;
            double highLat = lowLat + latUnit;
            double area = M_PI * (6370 * 6370) * (std::sin(highLat*M_PI/180) - std::sin(lowLat*M_PI/180)) * lonUnit;
            (*map)[i][j].area = area;
            (*map)[i][j].crimes = std::vector<crime>();
        }
    }
}

void buildMap(std::vector<std::vector<mapEntry>>* map, std::vector<crime>* crimeVector, doubleTuple lows, doubleTuple units) {
    for (crime crimeBuf : (*crimeVector)) {
        int segmentX = (int)((crimeBuf.lon - lows.d1) / units.d1);
        int segmentY = (int)((crimeBuf.lat - lows.d2) / units.d2);
        (*map)[segmentX][segmentY].crimes.push_back(crimeBuf);
    }
    for (int i = 0; i < finalWidth; i++) {
        for (int j = 0; j < finalHeight; j++) {
            (*map)[i][j].density = ((double)(*map)[i][j].crimes.size()) / (*map)[i][j].area;
            //std::cout << (*map)[i][j].density << std::endl;
        }
    }
    return;
}

cv::Vec3b colorFunction(double low, double high, double entry) {
    if (entry == 0) {
        return cv::Vec3b(0, 0, 0);
    }
    //std::cout << "NONZERO" << std::endl;
    double redDouble = ((dp(entry) - low) / (high - low) * 254);
    double greenDouble = (255 - (dp(entry) - low) / (high - low) * 254);
    uint8_t red = (uint8_t)redDouble;
    uint8_t green = (uint8_t)greenDouble;
    uint8_t blue = 0;
    return cv::Vec3b(blue, green, red);
}

void buildGraphic(std::vector<std::vector<mapEntry>>* map, cv::Mat* imageOutput, doubleTuple edges, double cut) {

    for (int i = 0; i < finalWidth; i++) {
        for (int j = 0; j < finalHeight; j++) {
            mapEntry entry = (*map)[i][j];
            if (entry.density > cut) {
                cv::Vec3b colorBuff = colorFunction(edges.d1, edges.d2, entry.density);
                (*imageOutput).at<cv::Vec3b>(j, i) = colorBuff;
            }
        }
    }
    return;
}

box globalBounds(std::vector<std::vector<crime>> allCrimeSets) {
    double lLon = 1000;
    double lLat = 1000;
    double hLon = 0;
    double hLat = 0;
    for (std::vector<crime> crimeVector : allCrimeSets) {
        box buf = findEdges(crimeVector);
        if (buf.minx < lLon) {
            lLon = buf.minx;
        }
        if (buf.maxx > hLon) {
            hLon = buf.maxx;
        }
        if (buf.miny < lLat) {
            lLat = buf.miny;
        } 
        if (buf.maxy > hLat) {
            hLat = buf.maxy;
        }
    }
    return box(lLon, lLat, hLon, hLat);
}

doubleTuple subDivideGrowBounds(box* bounds, int desiredWidth) {
    double lonRange = (*bounds).maxx - (*bounds).minx;
    double latRange = (*bounds).maxy - (*bounds).miny;
    double aspectRatio = lonRange / latRange;
    double height = (desiredWidth-4) / aspectRatio;

    double lonUnit = lonRange / (desiredWidth-4);
    double latUnit = latRange / height;

    finalWidth = (int)desiredWidth;
    finalHeight = (int)height + 4;

    (*bounds).miny -= 2 * latUnit;
    (*bounds).maxy += 2 * latUnit;
    (*bounds).minx -= 2 * lonUnit;
    (*bounds).maxx += 2 * lonUnit;
    return doubleTuple(lonUnit, latUnit);
}

doubleTuple findDensityLimits(std::vector<std::vector<std::vector<mapEntry>>> *allMaps) {
    double low = 1000000000;
    double high = 0;
    for (std::vector<std::vector<mapEntry>> map : (*allMaps)) {
        for (std::vector<mapEntry> column : map) {
            for (mapEntry entry : column) {
                if (entry.density != 0) {
                    if (entry.density > high) {
                        high = entry.density;
                    }
                    if (entry.density < low) {
                        low = entry.density;
                    }
                }
            }
        }
    }
    return doubleTuple(low, high);
}

std::vector<double> buildNonzeroEntries(std::vector<std::vector<mapEntry>> map) {
    std::vector<double> entryVector;
    for (std::vector<mapEntry> column : map) {
        for (mapEntry entry : column) {
            if (entry.density != 0) {
                entryVector.push_back(entry.density);
            }
        }
    }
    return entryVector;
}

std::vector<double> getCutOffs(std::vector<double> nonZeroes) {
    std::sort(nonZeroes.begin(), nonZeroes.end());
    std::vector<double> cutoffs;
    for (int i = 0; i < 20; i++) {
        cutoffs.push_back(nonZeroes[(int)(nonZeroes.size() / 20 * i)]);
    }
    return cutoffs;
}

std::string getFilename(std::string crimeType, int year, int month) {
    std::ostringstream fileName;
    fileName << "C:\\Users\\qenta\\multiOutCsv\\" << year << "-" << month << " " << crimeType << ".csv";
    return fileName.str();
}

int main() {

    std::vector<std::vector<std::vector<mapEntry>>> allMaps;
    
    int i = 1;

    std::cout << "Parsing files..." << std::endl;
    for (auto& dataDir : std::filesystem::directory_iterator(corePath)) {
        ParseFiles(dataDir.path().generic_string());
        allAllCrimes.push_back(allCrimes);
        allCrimes = std::vector<crime>();
    }

    std::cout << "Calculating map bounds..." << std::endl;
    box bounds = globalBounds(allAllCrimes);
    doubleTuple segments = subDivideGrowBounds(&bounds, 2000);

    std::cout << "Building maps..." << std::endl;
    for (std::vector<crime> crimeVector : allAllCrimes) {
        std::vector<std::vector<mapEntry>> fullMap(finalWidth, std::vector<mapEntry>(finalHeight, {}));
        initMap(&fullMap, doubleTuple(bounds.miny, bounds.maxy), segments.d2, segments.d1);
        buildMap(&fullMap, &crimeVector, doubleTuple(bounds.minx, bounds.miny), segments);
        allMaps.push_back(fullMap);
    }

    std::cout << "Caulculating density bounds..."<<std::endl;
    doubleTuple densityBounds = findDensityLimits(&allMaps);
    densityBounds.d1 = dp(densityBounds.d1);
    densityBounds.d2 = dp(densityBounds.d2);

    std::string base = "C:\\Users\\qenta\\multiOut\\";
    std::string end = ".png";

    std::cout << "Drawing maps..." << std::endl;
    for (std::vector<std::vector<mapEntry>> map : allMaps) {

        std::vector<std::string> openCrimeFilenames;
        std::vector<std::ofstream> crimeFiles;
        int year = (i + 2) / 12 + 2023;
        int month = (i + 2) % 12 + 1;

        std::cout << "Writing " << year << "-" << month << std::endl;

        int horc = 0;
        for (std::vector<mapEntry> line : map) {
            int verc = 0;
            for (mapEntry entry : line) {
                if (entry.crimes.size() > 0) {

                    std::vector<std::string> accountedCrimes;
                    std::vector<int> crimeCounts;

                    for (crime crimeEntry : entry.crimes) {
                        auto buf = std::find(accountedCrimes.begin(), accountedCrimes.end(), crimeEntry.type);
                        if (buf == accountedCrimes.end()) {
                            accountedCrimes.push_back(crimeEntry.type);
                            crimeCounts.push_back(1);

                            std::string bufferFilename = getFilename(crimeEntry.type, year, month);
                            auto buf2 = std::find(openCrimeFilenames.begin(), openCrimeFilenames.end(), bufferFilename);

                            if (buf2 == openCrimeFilenames.end()) {
                                openCrimeFilenames.push_back(bufferFilename);
                                crimeFiles.push_back(std::ofstream(bufferFilename));
                                crimeFiles[crimeFiles.size() - 1] << "Latitude lower bound, Longitude lower bound, Latitude upper bound, Longitude upper bound, Crime occurences, Area (km^2)" << std::endl;
                            }
                        }
                        else {
                            int id = std::distance(accountedCrimes.begin(), buf);
                            crimeCounts[id]++;
                        }


                    }
                    int j = 0;
                    for (std::string crimeType : accountedCrimes) {
                        std::string bufCrimeFile = getFilename(crimeType, year, month);

                        int id = std::distance(openCrimeFilenames.begin(), std::find(openCrimeFilenames.begin(), openCrimeFilenames.end(), bufCrimeFile));
                        crimeFiles[id] << segments.d1 * horc + bounds.minx << "," << segments.d2 * verc + bounds.miny << "," << segments.d1 * (horc + 1) + bounds.minx << "," << segments.d2 * (verc + 1) + bounds.miny << "," << crimeCounts[j] << "," << entry.area << std::endl;

                        j++;
                    }


                }
                verc++;
            }
            horc++;
        }

        for (int k = 0; k < crimeFiles.size();k++) {
            crimeFiles[k].close();
        }

        //std::vector<double> nonz = buildNonzeroEntries(map);
        //std::vector<double> cutOffs = getCutOffs(nonz);

        /*

        int j = 1;
        for (double cut : cutOffs) {
            cv::Mat img(finalHeight, finalWidth, CV_8UC3, cv::Scalar(0, 0, 0));
            buildGraphic(&map, &img, densityBounds, cut);
            cv::rotate(img, img, cv::ROTATE_90_COUNTERCLOCKWISE);
            std::ostringstream outfile;
            outfile << base << i <<"-"<<j<< end;
            std::cout << " Saving at " << outfile.str() << std::endl;
            cv::imwrite(outfile.str(), img);
            j++;
        }

        */

        i++;
    }
}