import sys
import time
import sys
import datetime
import argparse
import math
import datetime






global currentSIA 
	
global currentFNA

global SIALoc

global lastTSPos

global recordTS_Skip


#From stackoverflow
def read_in_chunks(file_object, chunk_size):
	"""Lazy function (generator) to read a file piece by piece.
	Default chunk size: 1k."""
	
	while True:
		data = file_object.read(chunk_size)
		if not data:
			break
		yield data


def bytesToDec(byteInput):
	tsString = byteInput[::-1].hex()
            
	decimalDate = int(tsString,16)

	return decimalDate


#Modified from https://forensicswiki.org/wiki/New_Technology_File_System_(NTFS)
def FromFiletime(filetime):

	if filetime < 0:
		return None
    

	if(filetime > 2147483647*10000000 + 116444736000000000):
		return "Invalid Timestamp"

	timestamp = filetime / 10

	dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=timestamp)

	stringTime = dt.ctime()

	stringTime += (" Microseconds " + str(dt.microsecond) + " (UTC)")
 
	return stringTime



#must be greater than one byte
def byteArrayToInt(byteArray):

	littleEndian = byteArray[::-1].hex()
	finalInt = int(littleEndian, 16)

	return finalInt



#Read out next FNA
def Next_FNA_Readout(f, data, relativeOffsetTS, offset, stringTime, page, pageSize):

	f.write("\nTimestamp: {}, FNA hit\n".format(stringTime))
	f.write("Byte Location (dec): {}\n".format(offset + (page * pageSize)))

	f.write("Start of File Name Attribute (FNA)\n") 
		
	filenameLength = int(data[relativeOffsetTS + 56])
	f.write("Filename: {}\n".format(data[(relativeOffsetTS + 58) : (relativeOffsetTS + 58 + 2*filenameLength):2]))

	printTimes(f, data, relativeOffsetTS)

	alloSizeFile = byteArrayToInt(data[(relativeOffsetTS + 32) : (relativeOffsetTS + 40)])

	logicSizeFile = byteArrayToInt(data[(relativeOffsetTS + 40) : (relativeOffsetTS + 42)])

	f.write("Allocated Size of File (dec): {}\n".format(alloSizeFile))
	f.write("Logical Size of File (dec): {}\n".format(logicSizeFile))

	f.write("Parent_ID: {}\n".format((data[(relativeOffsetTS - 8) : (relativeOffsetTS)]).hex()))

	f.write("End of File Name Attribute (FNA)\n\n") 


#simple function that prints the timestamps in a SIA or FNA attribute
def printTimes(f,data,locationFirstTimestamp):
	created = bytesToDec(data[locationFirstTimestamp : locationFirstTimestamp + 8])
	stringCreated = FromFiletime(created)
	modified = bytesToDec(data[locationFirstTimestamp + 8 : locationFirstTimestamp + 16])
	stringModified = FromFiletime(modified)
	mftmodified = bytesToDec(data[locationFirstTimestamp + 16  : locationFirstTimestamp + 24])
	stringMftmodified = FromFiletime(mftmodified)
	accessed = bytesToDec(data[locationFirstTimestamp + 24 : locationFirstTimestamp +32])
	stringAccessed = FromFiletime(accessed)
	f.write("Created: {}\n".format(stringCreated))
	f.write("Modified: {}\n".format(stringModified))
	f.write("MFT Modified: {}\n".format(stringMftmodified))
	f.write("Accessed: {}\n".format(stringAccessed))


#Recovery only checks the first two timestamps as starting locations of the matches, this is because there are some offset overlaps between SIAs and FNAs when needing to check relatively far
#off ranges.
def NTFS_FILEENTRY_RECOVERY(f, data, relativeOffsetTS, offset, page, pageSize):
	
	search = None
	attriTestSIA = None 
	attriTestSIAFNA = None
	attriTestFNA = None

	SIA = b'\x10\x00\x00\x00'
	FNA = b'0\x00\x00\x00'
	DA = b'\x80\x00\x00\x00'
	
	global SIALoc

	global recordTS_Skip

	filenameLength = 0

	pairSIAFNA = False

	global currentSIA 
	
	global currentFNA

	global lastTSPos


	#NTFS SPECIFIC
	attriTestSIA = data[(relativeOffsetTS - 24):(relativeOffsetTS - 20)]
	attriTestSIAFNA = data[(relativeOffsetTS - 32):(relativeOffsetTS - 28)]
	attriTestFNA = data[(relativeOffsetTS - 40):(relativeOffsetTS - 36)]

	decimalDate = bytesToDec(data[relativeOffsetTS: relativeOffsetTS + 8])
	
	#We ignore timestamps that occured before 1700
	if((decimalDate < 31241815320000000)   or (decimalDate > 189026359320000000)):
		return None


	stringTime = FromFiletime(decimalDate)

	#If we identified it as a SIA or possible FNA or SIA
	if ((attriTestSIA == SIA) or (attriTestSIAFNA == SIA)):
		f.write("\nTimestamp: {}, SIA hit\n".format(stringTime))
		f.write("Byte Location (dec): {}\n".format(offset + (page * pageSize)))
		currentSIA = True
		currentFNA = False
		if(attriTestSIA == SIA):
			SIALoc = relativeOffsetTS - 24
			tempOffset = offset - 24
		else:
			SIALoc = relativeOffsetTS - 32
			tempOffset = offset - 32

		lastTSPos = offset + (page * pageSize)

		f.write("Start of Standard Information Attribute (SIA)\n") 
		#  Print SIA timestamps, assuming second timestamp
		firstTimestampPos = SIALoc + 24
		printTimes(f, data, firstTimestampPos)
		#  End printing SIA timestamps
		f.write("End of Standard Information Attribute (SIA)\n") 


		#Setting up to find data attribute
		headerTest = b'\x00\x00\x00\x00'
		currentHeaderLoc = SIALoc
		safetyCounter  = 0
		FNAcount = 0


		#SIALoc might be the same as safetyCounter.  Update later.
		#While the header is not a data attribute, and we have not parsed some impossible length
		while( (headerTest != DA) and (currentHeaderLoc < (SIALoc + 968)) and (headerTest[0] < 128) and (safetyCounter < 1024)):
			
			headLength = byteArrayToInt(data[currentHeaderLoc + 4 : currentHeaderLoc + 8])
			currentHeaderLoc += headLength
			tempOffset += headLength
			headerTest = data[(currentHeaderLoc) : (currentHeaderLoc + 4)]

			#If it is an FNA
			if(headerTest == FNA):

				decimalDate = bytesToDec(data[currentHeaderLoc + 32: currentHeaderLoc + 32 + 8])
				stringTime = FromFiletime(decimalDate)

				#We may need to print out more FNAs
				Next_FNA_Readout(f, data, (currentHeaderLoc + 32), (tempOffset + 32), stringTime, page, pageSize)

				#Add TS locations to skip
				recordTS_Skip.append(tempOffset + 32 + (page*pageSize))
				FNAcount += 1

			safetyCounter += 1

		if((headerTest == DA) and (FNAcount > 0)):

			f.write("Start of Data Attribute \n")

			#If 0, then print out resident information.
			if(data[currentHeaderLoc + 8] == 0):

				resFileSize = data[currentHeaderLoc + 16 : currentHeaderLoc + 20]


				#Skip "RCRD" for $LogFile record header.
				if(resFileSize != b'\x52\x43\x52\x44'):

					correctWay = resFileSize[::-1].hex()
					rFS = int(correctWay,16)

					f.write("Resident Filesize: {}\n".format(rFS))

					resFileOffset = data[currentHeaderLoc + 20 : currentHeaderLoc + 22]
					correctWay = resFileOffset[::-1].hex()
					rFO = int(correctWay,16)
					f.write("Resident File: ")
										
					#For resident file print out as much ascii as we can.
					for r in range(rFS):
						if(data[(currentHeaderLoc + rFO + r)] < 128):
							f.write(str(chr(data[(currentHeaderLoc + rFO + r)])))
						else:
							f.write("\\{}".format(hex(data[(currentHeaderLoc + rFO + r)])))
					f.write("\n\n")

				else:
					f.write("Non-standard RCRD Data. Skipping typical output.\n\n")

			#If it is not resident...
			else:

				unitCompressionSize = byteArrayToInt(data[currentHeaderLoc + 34: currentHeaderLoc + 36])
				allocSizeAttriContent = byteArrayToInt(data[currentHeaderLoc + 40:currentHeaderLoc + 48])
				actualSizeAttribContent = byteArrayToInt(data[currentHeaderLoc + 48:currentHeaderLoc + 56])
				initializedSizeAttrib = byteArrayToInt(data[currentHeaderLoc + 56 :currentHeaderLoc + 64])

				f.write("Unit compression size: {}\n".format(unitCompressionSize))

				f.write("Allocated size of attribute content: {}\n".format(allocSizeAttriContent))

				f.write("Actual size of attribute content: {}\n".format(actualSizeAttribContent))

				f.write("Initialized size of attribute content: {}\n".format(initializedSizeAttrib))

				dataRunLoc = data[currentHeaderLoc + 32]

				#DataRun Logic.
				nibbles = data[currentHeaderLoc + dataRunLoc]
				relativeDataAttr = dataRunLoc

				#Iterate over runs
				while ((nibbles != 0) and relativeDataAttr < 1024):
					relativeDataAttr += ((nibbles >> 4) + (nibbles & 15) + 1)
					nibbles = data[currentHeaderLoc + relativeDataAttr]

				f.write("DataRun: {}\n\n".format((data[(currentHeaderLoc + dataRunLoc) : (currentHeaderLoc + relativeDataAttr )]).hex()))

			if(data[currentHeaderLoc + 8] == 0):
				f.write("\nFile content is fully recoverable if resident file size is larger than 0\n")
			else:
				f.write("\nFile content is potentially recoverable (non-resident content)\n")
			currentSIA = False
			currentFNA = False
			relativeOffsetTS = SIALoc + 968

			f.write("End of Data Attribute \n")
	
			#This signifies we found some SIA+FNA+DA combination
			f.write("************************************************************\n")



	#If it is identified as an FNA or possible SIA/FNA
	elif ((attriTestFNA == FNA) or (attriTestSIAFNA == FNA)):


		f.write("\nTimestamp: {}, FNA hit\n".format(stringTime))
		f.write("Byte Location (dec): {}\n".format(offset + (page * pageSize)))


		#From second timestamp
		if(attriTestFNA == FNA):
			f.write("Start of File Name Attribute (FNA)\n")
			filenameLength = int(data[relativeOffsetTS + 48])
			f.write("Filename: {}\n".format(data[(relativeOffsetTS + 50) : (relativeOffsetTS + 50 + 2*filenameLength):2]))

			# Print FNA timestamps, assuming second timestamp
			firstTimestampPos = relativeOffsetTS - 8
			printTimes(f, data, firstTimestampPos)
			# End printing FNA timestamps

			alloSizeFile = byteArrayToInt(data[(relativeOffsetTS + 24) : (relativeOffsetTS + 32)])

			logicSizeFile = byteArrayToInt(data[(relativeOffsetTS + 32) : (relativeOffsetTS + 34)])

			f.write("Allocated Size of File (dec): {}\n".format(alloSizeFile))

			f.write("Logical Size of File (dec): {}\n".format(logicSizeFile))

			f.write("Parent_ID: {}\n".format((data[(relativeOffsetTS - 16) : (relativeOffsetTS - 8)]).hex()))
			f.write("End of File Name Attribute (FNA)\n\n")


		#from first timestamp
		else:
			f.write("Start of File Name Attribute (FNA)\n")
			filenameLength = int(data[relativeOffsetTS + 56])
			f.write("Filename: {}\n".format(data[(relativeOffsetTS + 58) : (relativeOffsetTS + 58 + 2*filenameLength):2]))
			
			# Print FNA timestamps, assuming first timestamp
			firstTimestampPos = relativeOffsetTS
			printTimes(f, data, firstTimestampPos)
			# End printing FNA timestamps

			alloSizeFile = byteArrayToInt(data[(relativeOffsetTS + 32) : (relativeOffsetTS + 40)])

			logicSizeFile = byteArrayToInt(data[(relativeOffsetTS + 40) : (relativeOffsetTS + 42)])

			f.write("Allocated Size of File (dec): {}\n".format(alloSizeFile))

			f.write("Logical Size of File (dec): {}\n".format(logicSizeFile))

			f.write("Parent_ID: {}\n".format((data[(relativeOffsetTS - 8) : (relativeOffsetTS)]).hex()))
			f.write("End of File Name Attribute (FNA)\n\n")

		currentFNA = True



#Need to reconstruct this but using memory mapping.  This mostly handles the reading in of large files in smaller memory pages.
def main(timestamps, fileLoc):    

	#This is the page size
	chunk_size = 8388608

	#Set possible prepend size
	prepend = 0

	#Read in list of timestamps, turn it into a list of ints
	timeList = [int(line.rstrip('\n')) for line in open(timestamps)]

	#Keeps track of byte location
	byteLocation = 0

	#Setting up var for later use
	totalLocation = 0

	#initialized here for C++ memory issues
	matchCount = 0

	#This is the threshold Iterator
	i = 0

	#Keeps track of chunk/page count
	currentPageNumber= 0

	#Did we add the end of the page to the next page?
	prependAHEAD = False

	#Did we add the end of the page from the previous page?
	prependLAST = False

	#Need to keep track of timestamps to skip
	global recordTS_Skip
	recordTS_Skip = []

	#Need to keep track if we are "in range" of a SIA
	global currentSIA 
	currentSIA = False
	
	#Need to keep track if we are "in range" of a FNA
	global currentFNA
	currentFNA = False

	#Need to keep track of where the SIA is (if it is too far from an FNA, we probably aren't reading an attribute)
	global SIALoc
	SIALoc = 0

	#Keep track of the last timestamp position.
	global lastTSPos
	lastTSPos = 0

	#File we write to and read from.
	f = open("NTFSResults.txt", "w")
	g = open(fileLoc, "rb")

	#Read a page for the start.
	page = g.read(chunk_size)

	#Set a temporary size, it may change depending on if we have prepended.
	tempChunkSize = chunk_size

	#Following is just to calculate progress...
	timestampCount = len(timeList)
	ten = True
	twen = True
	thir = True
	fort = True
	fift = True
	sixt = True
	seve = True
	eigh = True
	nint = True
	fini = True

	#Set variable if we need to skip the timestamp since we have already read it from some FNA
	skipStamp = False

	for i in range(len(timeList)):
		


		skipStamp = False

		#checks for repeating timestamps
		for ii in range(len(recordTS_Skip)):
			if(abs(timeList[i] - recordTS_Skip[ii] <= 16)):

				skipStamp = True
				del recordTS_Skip[ii]
				break

		#If we haven't been instructed to skip, we do it normally.
		if(skipStamp == False):
			
			#Get's the TS Location
			TSLoc = timeList[i]

			#Calculates TRUE page number
			timePageNumber = math.floor(TSLoc / chunk_size)
			
			#Calculates Offest (may change with prepending)
			pageOffset = TSLoc % chunk_size

			#Keep True offset
			realOffset = pageOffset

			#For giving progress reports
			timePercentage = i/timestampCount
			if(timePercentage > 0.1 and timePercentage < .2 and ten):
				print("Ten Percent Done\n")
				ten = False
			elif(timePercentage > 0.2 and timePercentage < .3 and twen):
				print("Twenty Percent Done\n")
				twen = False
			elif(timePercentage > 0.3 and timePercentage < .4 and thir):
				print("Thirty Percent Done\n")
				thir = False
			elif(timePercentage > 0.4 and timePercentage < .5 and fort):
				print("Forty Percent Done\n")
				fort = False
			elif(timePercentage > 0.5 and timePercentage < .6 and fift):
				print("Fifty Percent Done\n")
				fift = False
			elif(timePercentage > 0.6 and timePercentage < .7 and sixt):
				print("Sixty Percent Done\n")
				sixt = False
			elif(timePercentage > 0.7 and timePercentage < .8 and seve):
				print("Seventy Percent Done\n")
				seve = False
			elif(timePercentage > 0.8 and timePercentage < .9 and eigh):
				print("Eighty Percent Done\n")
				eigh = False
			elif(timePercentage > 0.9 and timePercentage < 1 and nint):
				print("Ninety Percent Done\n")
				nint = False


			if(timePageNumber - currentPageNumber > 1):
				if(prependAHEAD):
					currentPageNumber += 1
				prependAHEAD = False
				prependBehind = False


			#This is for looking in the center
			if((pageOffset > 1024) and (pageOffset < (chunk_size - 1024))):

				if(prependAHEAD and (timePageNumber - currentPageNumber == 1)):

					currentPageNumber += 1
					prependAHEAD = False

				else:
					if(prependAHEAD):
							currentPageNumber += 1
							prependAHEAD = False 
					for k in range(timePageNumber - currentPageNumber):
						page = g.read(chunk_size)
						currentPageNumber += 1
						prepend = 0
						prependAHEAD = False
						prependLAST = False
						tempChunkSize = chunk_size
						if not page:
							break

				prependAHEAD = False
				pageOffset += prepend

				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)



			#This is for timestamps at the beginning of the page
			elif((pageOffset >= 0) and (pageOffset <= 1024) and (currentPageNumber != 0) and (timePageNumber != currentPageNumber) and (prependAHEAD == False)):


				for k in range(timePageNumber - currentPageNumber - 1):
					page = g.read(chunk_size)
					currentPageNumber += 1
					tempChunkSize = chunk_size
					if not page:
						break

				page = page[-1024::]

				#Add new page.
				page += g.read(chunk_size)

				#You add plus one, since you already got the info from before.  TSpage should be same as CPage.
				currentPageNumber += 1


				#This should be our prepend value.
				prepend = 1024
				tempChunkSize = chunk_size + prepend

				#We took info from the previous page.
				prependLAST = True

				#must account for those 1024 bytes
				pageOffset += prepend

				
				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)



			#At start of page, but we have already prepended of the same type.  Furthermore, we are still on the same page.
			elif((pageOffset >= 0) and (pageOffset <= 1024) and (currentPageNumber != 0) and (timePageNumber == currentPageNumber) and (prependLAST)):
				pageOffset += prepend

				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)


			elif((pageOffset >= (chunk_size - 1024)) and (prependAHEAD == False)):

				for k in range(timePageNumber - currentPageNumber):
					page = g.read(chunk_size)
					currentPageNumber += 1
					tempChunkSize = chunk_size
					if not page:
						break


				#Gets you end of last chunk/page
				page = page[tempChunkSize - 1064: tempChunkSize]

				#Big difference here is that we have "not gone to the next page" 
				page += g.read(chunk_size)

				prepend = 1064

				#The last size, minus the offset, plus the prepend
				pageOffset = (prepend - (chunk_size - pageOffset)) 

				#This sets the forward chunk 
				tempChunkSize = chunk_size + prepend

				prependAHEAD = True
				prependLAST = False


				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)



			#only triggers when the difference between pages is 1.
			elif((pageOffset >= (chunk_size - 1024)) and (prependAHEAD == True) and (timePageNumber > currentPageNumber)):
				
				currentPageNumber += 1


				for k in range(timePageNumber - currentPageNumber):
					page = g.read(chunk_size)
					currentPageNumber += 1
					tempChunkSize = chunk_size
					if not page:
						break

				
				#Gets you end of last chunk/page
				page = page[tempChunkSize - 1064: tempChunkSize]

				#Big difference here is that we have "not gone to the next page" 
				page += g.read(chunk_size)

				prepend = 1064

				#The last size, minus the offset, plus the prepend
				pageOffset = (prepend - (chunk_size - pageOffset)) 

				#This sets the forward chunk 
				tempChunkSize = chunk_size + prepend

				prependAHEAD = True
				prependLAST = False


				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)



			#we have prepended from ahead		
			#We need a new page variable
			#This is using an old page
			#Basically, we are already looking at the "prepended" part
			elif( (pageOffset >= (chunk_size - 1024)) and (prependAHEAD == True) and (currentPageNumber == timePageNumber)):
				
				pageOffset = (prepend - (chunk_size - pageOffset))

				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)


			elif( ((pageOffset >= 0) and (pageOffset <= 1024) and (currentPageNumber != 0)  and (timePageNumber - currentPageNumber == 1) and (prependAHEAD == True))):
				

				#only difference is the non-change in page number.
				if(currentPageNumber < timePageNumber):
					currentPageNumber += 1

				pageOffset = (prepend + pageOffset)

				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)


				prependAHEAD = False

			elif( ((pageOffset >= 0) and (pageOffset <= 1024) and (currentPageNumber != 0)  and (timePageNumber ==  currentPageNumber) and (prependAHEAD == False))):
	

				pageOffset = (prepend + pageOffset)

				NTFS_FILEENTRY_RECOVERY(f, page, pageOffset, realOffset, timePageNumber, chunk_size)


	f.close()

	g.close()










if __name__ == '__main__':


	main(sys.argv[1],sys.argv[2])
