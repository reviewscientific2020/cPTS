#include <system_error> // for std::error_code
#include <fstream>
#include <ctime>
#include <stdio.h>
#include <string>
#include "date.h"
#include <vector>
#include <math.h>  

//Additional libraries
#include <mio/mmap.hpp>
#include "anyoption.h"


//What is this?

//Declaring methods
int handle_error(const std::error_code& error);

//https://stackoverflow.com/questions/46033813/c-converting-datetime-to-timestamp
//https://github.com/HowardHinnant/date/blob/master/include/date/date.h
//We obtain Unix time, convert it to NTFS time if need be.
date::sys_seconds to_sys_time(unsigned char y, unsigned char m, unsigned char d,
	unsigned char h, unsigned char M, unsigned char s)
{
	using namespace date;
	using namespace std::chrono;
	return sys_days{ year{ y + 2000 } / m / d } +hours{ h } +minutes{ M } +seconds{ s };
}


//This is to split input strings
//http://www.cplusplus.com/articles/2wA0RXSz/
const std::vector<std::string> explode(const std::string& s, const char& c)
{
	std::string buff{ "" };
	std::vector<std::string> v;

	for (auto n : s)
	{
		if (n != c) buff += n; else
			if (n == c && buff != "") { v.push_back(buff); buff = ""; }
	}
	if (buff != "") v.push_back(buff);

	return v;
}


//Most everything runs inside main
int main(int argc, char** argv)
{

	//TimeRange is switch to limit timestamp comparisons.
	//InRange is the bool which tests it.  -t flag will set it to true.
	bool timeRange = false;

	//Default is true, as it allows us to search without considering time range
	bool inRange = true;

	//AnyOption 1.3 kishan at hackorama dot com  www.hackorama.com JULY 2001
	//Command line functionality
	AnyOption *opt = new AnyOption();

	opt->addUsage("This program is meant to identify timestamps in filesystem metadata.  It does not require minimum or maximum timestamps ranges, or even an assumption of the datetime formatting.  This is due to the fact that the timestamp identifcation is based upon simple byte matching.");

	//Defining flags
	opt->setFlag("help", 'h');
	opt->setFlag("timeRange", 't');
	//opt->setOption("data");
	
	opt->processCommandArgs(argc, argv);

	if (opt->getFlag("help") || opt->getFlag('h')) {
		printf("The arguments for this program are the required arguments:\n\n<disk image location> <timestamp size> <search threshold> <number of timestamps that should be the same>\n\nAnd the optional arguments:\n\n<min date> <max date> <-t>\n\n-t is for limiting matches between NTFS dates.\n");
		opt->printAutoUsage();
		return 0;
	}

	//Set time range to true if t flag set
	if (opt->getFlag('t')) {
		timeRange = true;
	}
	

	if(argv[1] == 0 || argv[2] == 0 || argv[3] == 0 || argv[4] == 0){
		std::cout << "Missing mandatory arguments, see -help for details." << std::endl;
		exit(1);
	}
	
	//For timing
	clock_t begin = clock();

	//This is the output file of the timestamp locations.
	std::ofstream myfile;
	myfile.open("cPTS.txt");

	//Memory mapping with c++
	std::error_code error;

	//Taking in arguments from command line
	std::string inputDD = argv[1];

	int searchSize = std::stoi(argv[2]);
	int threshold = std::stoi(argv[3]);
	int mcThresh = std::stoi(argv[4]);
	
	//Declare min/max variables just in case.
	long long int minHold;
	long long int maxHold;


	//If the time range is set, then we need to obtain them in an 8 byte representation.	
	//This is to set time range
	//Check later for bugs
	if ((argv[5] != 0) && (timeRange == true)) {
		std::string minString = argv[6];  //was 5
		std::string maxString = argv[7];  //was 6

		//Obtain vectors of the dates.
		std::vector<std::string> minVec{ explode(minString, '-') };

		std::vector<std::string> maxVec{ explode(maxString, '-') };

		//Setting converting min/max dates assuming Unix/NTFS/FAT.
		//FAT timestamps is a work in progress
		if (searchSize == 2) {
			//Work in progress

			std::cout << "work in progress"<< std::endl;
			exit(1);
		}
		else if ((searchSize == 4) || (searchSize == 8)) {

			minHold = to_sys_time(std::stoi(minVec[0]) - 2000, std::stoi(minVec[1]), std::stoi(minVec[2]), std::stoi(minVec[3]), std::stoi(minVec[4]), std::stoi(minVec[5])).time_since_epoch().count();

			maxHold = to_sys_time(std::stoi(maxVec[0]) - 2000, std::stoi(maxVec[1]), std::stoi(maxVec[2]), std::stoi(maxVec[3]), std::stoi(maxVec[4]), std::stoi(maxVec[5])).time_since_epoch().count();

			//Conversion of unix to NTFS
			if (searchSize == 8) {
				minHold = minHold * 10000000 + 116444736000000000;
				maxHold = maxHold * 10000000 + 116444736000000000;
			}

		}
		else {
			std::cout << "Only timestamps of length 2, 4, and 8 are supported." << std::endl;
			exit(1);
		}
	}


	//Just getting filesize
	std::ifstream in_file(inputDD, std::ios::binary | std::ios::ate);
	double mSize = in_file.tellg();
	in_file.close();
	
	
	const size_t OneGigabyte = 1 << 30;

	mio::mmap_source ro_mmap;
	
	if(mSize < OneGigabyte){
		ro_mmap.map(inputDD, error);
		if (error) { return handle_error(error); }
	}else{
		
		ro_mmap.map(inputDD, 0, OneGigabyte, error);
		if (error) { return handle_error(error); }
	
	}

	//Variables for timestamps initialization
	unsigned long long search = 0;
	unsigned long long testBlock = 0;

	//Initializing counter
	int matchCount = 0;

	//Initialization bool ensuring repeat sequence of bytes cannot happen 0x0000 and 0xffff etc.
	bool repeat = true;


	//std::cout << mSize;
	bool ten = true;
	bool twe = true;
	bool thir = true;
	bool fort = true;
	bool fif = true;
	bool six = true;
	bool sev = true;
	bool eig = true;
	bool nin = true;


	//Used to calculate last page
	unsigned long long GBCounter = 1;
	
	//Used to calculate last page
	unsigned long long maxGB = ((unsigned long long)mSize)/OneGigabyte;
	
	//Indexes pages loaded into memory
	unsigned long long gbqq = 0;

	//For below conditionals
	bool tripBit = true;
	
		
	//Loops through all bytes in the images, while flipping through memory pages
	//Increasing by searchsize.
	for (unsigned long long qq = 0; qq < (mSize - threshold); qq += searchSize) {

		//This should fix size issue
		if((qq % OneGigabyte >= 0)  && (qq % OneGigabyte <= threshold)){
			tripBit = true;
		} 

		//This is the counter in the GRAND scheme of things (not relative per GB).  
		//Basically, if we are in the last 64K? bytes, we should do something.
		if (((qq % OneGigabyte) > (OneGigabyte - 0x1000)) && tripBit) {

			//If its the last chunk, we need smaller than a GB.
			if(GBCounter >= maxGB){
				ro_mmap.map(inputDD, qq, mSize - qq, error);
				if (error) { return handle_error(error); }
			}else{
				ro_mmap.map(inputDD, qq, OneGigabyte, error);
				if (error) { return handle_error(error); }
			}
		
			gbqq = 0;
			
			std::cout << GBCounter << std::endl;
			
			GBCounter += 1;
			tripBit = false;
		}
		

		//Progress bar
		if (((qq / mSize) > .1) && (ten)) {

			ten = false;

			std::cout << "Ten percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .2) && (twe)) {

			twe = false;
			std::cout << "Twenty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .3) && (thir)) {

			thir = false;
			std::cout << "Thirty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .4) && (fort)) {

			fort = false;
			std::cout << "Forty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .5) && (fif)) {
			fif = false;

			std::cout << "Fifty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .6) && (six)) {
			six = false;

			std::cout << "Sixty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		
		else if (((qq / mSize) > .7) && (sev)) {
			sev = false;

			std::cout << "Seventy percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .8) && (eig)) {
			eig = false;

			std::cout << "Eighty percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";

		}
		else if (((qq / mSize) > .9) && (nin)) {
			nin = false;

			std::cout << "Ninety percent passed\n";

			clock_t mid = clock();
			double elapsed_secs = double(mid - begin) / CLOCKS_PER_SEC;
			std::cout << elapsed_secs;
			std::cout << "\n";
		}

		//Value resets
		repeat = true;

		//Get timestamp search string.
		//For the possible timestamps (only 8, 4, 2 right now).
		if (searchSize == 8) {
			//These internal loops check for repeated sequences of bytes.
			for (int r = 1; r < 8; r++) {
				repeat = repeat and (ro_mmap[gbqq] == ro_mmap[gbqq + r]);
			}
			//We are constructing longs from the individual bytes
			search = ((unsigned long long)(((unsigned char)ro_mmap[gbqq]))) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 1]))) << 8) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 2]))) << 16) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 3]))) << 24) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 4]))) << 32) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 5]))) << 40) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 6]))) << 48) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 7]))) << 56);
		}
		else if (searchSize == 4) {
			for (int r = 1; r < 4; r++) {
				repeat = repeat and (ro_mmap[gbqq] == ro_mmap[gbqq + r]);
			}
			search = ((unsigned long long)(((unsigned char)ro_mmap[gbqq]))) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 1]))) << 8) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 2]))) << 16) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 3]))) << 24);
		}
		else if (searchSize == 2) {
			for (int r = 1; r < 2; r++) {
				repeat = repeat and (ro_mmap[gbqq] == ro_mmap[gbqq + r]);
			}
			search = ((unsigned long long)(((unsigned char)ro_mmap[gbqq]))) | (((unsigned long long)(((unsigned char)ro_mmap[gbqq + 1]))) << 8);
		}
		else {
			std::cout << "Only timestamps of length 2, 4, and 8 are supported." << std::endl;
			exit(1);
		}

		//If the time flag was set, we need to check if the potential timestamp falls between these dates.
		if (timeRange) {
			inRange = ((minHold <= search) & (maxHold >= search));
		}

		//Continue if not repeated sequences of bytes and in range (if enabled).  Basically, prefix shouldn't be 0.
		if (!repeat && inRange ) {

			//reset matchCount
			matchCount = 0;

			//Internal loop to search through threshold
			for (int jj = (gbqq + searchSize); jj < (gbqq + searchSize + threshold); jj += searchSize) {

				//same treatment for the test block.
				if (searchSize == 8) {
					testBlock = ((unsigned long long)(((unsigned char)ro_mmap[jj]))) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 1]))) << 8) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 2]))) << 16) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 3]))) << 24) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 4]))) << 32) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 5]))) << 40) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 6]))) << 48) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 7]))) << 56);
				}
				else if (searchSize == 4) {
					testBlock = ((unsigned long long)(((unsigned char)ro_mmap[jj]))) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 1]))) << 8) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 2]))) << 16) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 3]))) << 24);
				}
				else if (searchSize == 2) {
					testBlock = ((unsigned long long)(((unsigned char)ro_mmap[jj]))) | (((unsigned long long)(((unsigned char)ro_mmap[jj + 1]))) << 8);
				}

			
				//If they are the same, increase matchcount.
				if (search == testBlock) {
					matchCount += 1;
				}

				//If above threshold, mark position.
				if (matchCount >= (mcThresh - 1)) {

					//Write out to file. 
					myfile << qq;
					myfile << "\n";

					//End internal loop
					jj += 10000;

					//Prevent getting duplicate timestamps
					qq += threshold - searchSize;
					gbqq += threshold - searchSize;
				}
			
			}
		}

		//move search pointer forward by searchstring size
		gbqq += searchSize;

	}

	//close write file.
	myfile.close();

	//Write out time used
	clock_t end = clock();
	double elapsed_secs = double(end - begin) / CLOCKS_PER_SEC;
	std::cout << elapsed_secs;

	return 0;
}


//Error handling method from MIO source
int handle_error(const std::error_code& error)
{
	const auto& errmsg = error.message();

	std::printf("error mapping file: %s, exiting...\n", errmsg.c_str());


	return error.value();
}