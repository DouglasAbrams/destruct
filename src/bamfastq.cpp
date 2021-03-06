/*
 *  bamfastq.cpp
 *
 *  Created by Andrew McPherson on 28/09/09.
 *
 */

#include "DebugCheck.h"
#include "Indexer.h"
#include "AlignmentStream.h"
#include "RegionDB.h"
#include "api/BamReader.h"

#include <fstream>
#include <iostream>
#include <string>
#include <map>
#include <set>
#include <tclap/CmdLine.h>
#include <boost/algorithm/string.hpp>
#include <boost/accumulators/accumulators.hpp>
#include <boost/accumulators/statistics/stats.hpp>
#include <boost/accumulators/statistics/min.hpp>
#include <boost/accumulators/statistics/max.hpp>
#include <boost/accumulators/statistics/mean.hpp>
#include <boost/accumulators/statistics/variance.hpp>

using namespace boost;
using namespace std;

using namespace BamTools;


struct ReadData
{
	ReadData(const string& sequence, const string& qualities, bool failedQC) : sequence(sequence), qualities(qualities), failedQC(failedQC) {}
	string sequence;
	string qualities;
	bool failedQC;
};


inline string GetSequence(const BamAlignment& alignment)
{
	string sequence = alignment.QueryBases;
	if (alignment.IsReverseStrand())
	{
		ReverseComplement(sequence);
	}
	return sequence;
}

inline string GetQualities(const BamAlignment& alignment)
{
	string qualities = alignment.Qualities;
	if (alignment.IsReverseStrand())
	{
		reverse(qualities.begin(), qualities.end());
	}
	return qualities;
}

int main(int argc, char* argv[])
{
	string bamFilename;
	string fastq1Filename;
	string fastq2Filename;
	bool rename;
	
	try
	{
		TCLAP::CmdLine cmd("Bam to Fastq Tool");
		TCLAP::ValueArg<string> bamFilenameArg("b","bam","Bam Filename",true,"","string",cmd);
		TCLAP::ValueArg<string> fastq1FilenameArg("1","fastq1","Fastq End 1 Filename",true,"","string",cmd);
		TCLAP::ValueArg<string> fastq2FilenameArg("2","fastq2","Fastq End 2 Filename",true,"","string",cmd);
		TCLAP::SwitchArg renameArg("r","rename","Rename With Integer IDs",cmd);
		cmd.parse(argc,argv);
		
		bamFilename = bamFilenameArg.getValue();
		fastq1Filename = fastq1FilenameArg.getValue();
		fastq2Filename = fastq2FilenameArg.getValue();
		rename = renameArg.getValue();
	}
	catch (TCLAP::ArgException &e)
	{
		cerr << "error: " << e.error() << " for arg " << e.argId() << endl;
		exit(1);
	}
	
	ofstream fastq1File(fastq1Filename.c_str());
	ofstream fastq2File(fastq2Filename.c_str());
	
	CheckFile(fastq1File, fastq1Filename);
	CheckFile(fastq2File, fastq2Filename);
	
	ofstream* fastqFiles[2];
	fastqFiles[0] = &fastq1File;
	fastqFiles[1] = &fastq2File;
	
	unordered_map<string,ReadData> readBuffer[2];
	
	BamReader bamReader;
	if (!bamReader.Open(bamFilename))
	{
		cerr << "Error: Unable to open bam file " << bamFilename << endl;
		exit(1);
	}
	
	int fragmentIndex = 0;
	BamAlignment alignment;
	while (bamReader.GetNextAlignment(alignment))
	{
		int readEnd = alignment.IsFirstMate() ? 0 : 1;
		int otherReadEnd = OtherReadEnd(readEnd);
		
		string sequence = GetSequence(alignment);
		string qualities = GetQualities(alignment);
		
		unordered_map<string,ReadData>::iterator otherEndIter = readBuffer[otherReadEnd].find(alignment.Name);
		
		if (otherEndIter != readBuffer[otherReadEnd].end())
		{
			if (!alignment.IsFailedQC() && !otherEndIter->second.failedQC)
			{
				string fragment = alignment.Name;
				
				if (rename)
				{
					stringstream fragmentStream;
					fragmentStream << fragmentIndex;
					fragment = fragmentStream.str();
				}
				
				*fastqFiles[readEnd] << "@" << fragment << "/" << readEnd + 1 << endl;
				*fastqFiles[readEnd] << sequence << endl;
				*fastqFiles[readEnd] << "+" << alignment.Name << endl;
				*fastqFiles[readEnd] << qualities << endl;
				
				*fastqFiles[otherReadEnd] << "@" << fragment << "/" << otherReadEnd + 1 << endl;
				*fastqFiles[otherReadEnd] << otherEndIter->second.sequence << endl;
				*fastqFiles[otherReadEnd] << "+" << alignment.Name << endl;
				*fastqFiles[otherReadEnd] << otherEndIter->second.qualities << endl;
				
				fragmentIndex++;
			}
			
			readBuffer[otherReadEnd].erase(otherEndIter);
		}
		else
		{
			readBuffer[readEnd].insert(make_pair(alignment.Name, ReadData(sequence, qualities, alignment.IsFailedQC())));
		}
	}
}

