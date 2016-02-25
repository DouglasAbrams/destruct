/*
 *  bampartition.cpp
 *
 */

#include "Common.h"
#include "DebugCheck.h"

#include <fstream>
#include <iostream>
#include <string>
#include <tclap/CmdLine.h>
#include <bamtools/api/BamReader.h>
#include <bamtools/api/BamWriter.h>
#include <boost/unordered_map.hpp>

using namespace boost;
using namespace std;

using namespace BamTools;


int main(int argc, char* argv[])
{
	string bamInputFilename;
	string bamOutputAFilename;
	string bamOutputBFilename;
	double fractionA;
	
	try
	{
		TCLAP::CmdLine cmd("Bam Partitioning");
		TCLAP::ValueArg<string> bamInputFilenameArg("i","inbam","Input Bam Filename",true,"","string",cmd);
		TCLAP::ValueArg<string> bamOutputAFilenameArg("a","abam","Output Bam A Filename",true,"","string",cmd);
		TCLAP::ValueArg<string> bamOutputBFilenameArg("b","bbam","Output Bam B Filename",true,"","string",cmd);
		TCLAP::ValueArg<double> fractionAArg("f","fracta","Fraction of A Reads",true,0.5,"float",cmd);
		cmd.parse(argc,argv);
		
		bamInputFilename = bamInputFilenameArg.getValue();
		bamOutputAFilename = bamOutputAFilenameArg.getValue();
		bamOutputBFilename = bamOutputBFilenameArg.getValue();
		fractionA = fractionAArg.getValue();
	}
	catch (TCLAP::ArgException &e)
	{
		cerr << "error: " << e.error() << " for arg " << e.argId() << endl;
		exit(1);
	}
	
	srand(2013);
	
	BamReader bamInput;
	if (!bamInput.Open(bamInputFilename))
	{
		cerr << "Error: Unable to read bam file " << bamInputFilename << endl;
		exit(1);
	}
	
	BamWriter bamOutputA;
	if (!bamOutputA.Open(bamOutputAFilename, bamInput.GetHeader(), bamInput.GetReferenceData()))
	{
		cerr << "Error: Unable to write to bam file " << bamOutputAFilename << endl;
		exit(1);
	}
	
	BamWriter bamOutputB;
	if (!bamOutputB.Open(bamOutputBFilename, bamInput.GetHeader(), bamInput.GetReferenceData()))
	{
		cerr << "Error: Unable to write to bam file " << bamOutputBFilename << endl;
		exit(1);
	}

	unordered_map<string,bool> readIsA;

	BamAlignment alignment;
	while (bamInput.GetNextAlignment(alignment))
	{
		alignment.RemoveTag("RG");

		unordered_map<string,bool>::const_iterator readIsAIter = readIsA.find(alignment.Name);

		bool firstInPair = false;

		// Read name has not been seen yet
		if (readIsAIter == readIsA.end())
		{
			float r = static_cast<float>(rand()) / static_cast<float>(RAND_MAX);

			bool isA = false;
			if (r < fractionA)
			{
				isA = true;
			}

			readIsAIter = readIsA.insert(make_pair(alignment.Name, isA)).first;

			firstInPair = true;
		}

		// Add to correct bam
		if (readIsAIter->second)
		{
			bamOutputA.SaveAlignment(alignment);
		}
		else
		{
			bamOutputB.SaveAlignment(alignment);
		}

		// No need to remember decision if last in pair
		if (!firstInPair)
		{
			readIsA.erase(readIsAIter);
		}
	}
}


