/*
 *  AlignmentProbability.h
 *
 */

#ifndef ALIGNMENTPROBABILITY_H_
#define ALIGNMENTPROBABILITY_H_

#include "Common.h"


class AlignmentProbability
{
public:
	AlignmentProbability(int matchScore) : mMatchScore(matchScore) {}
	
	void ReadDistributions(const string& filename);
	
	double ProbTrue(int alignedLength, int score) const;
	double ProbInvalid(int alignedLength, int score) const;
	double ProbFalse(int alignedLength, int score) const;
	double Classify(int alignedLength, int score, double prior) const;
	
private:
	int mMatchScore;
	DoubleMap mMixWeight;
	DoubleMap mNBSizeTrue;
	DoubleMap mNBProbTrue;
	DoubleMap mNBSizeInvalid;
	DoubleMap mNBProbInvalid;
};


class AlignmentPosterior
{
public:
	AlignmentPosterior()
	: mAlignmentProbability(0), mAlignedLength(0), mMaxScore(0), mSumProbTrue(0.0) {}
	
	void Initialize(const AlignmentProbability* alignmentProbability, int alignedLength);
	
	void AddAlignment(int score);
	
	double MaxPosterior();
	double Posterior(int score);
	
private:
	const AlignmentProbability* mAlignmentProbability;
	int mAlignedLength;
	int mMaxScore;
	double mSumProbTrue;
};


#endif


