import sys
import argparse
import mmap 
import os
import math
import datetime
import csv


try:
    from StringIO import StringIO ## for Python 2
except ImportError:
    from io import StringIO ## for Python 3

import time 

#Change bytes to decimal
def bytesToDec(byteInput):
    tsString = byteInput[::-1].hex()
            
    decimalDate = int(tsString,16)

    return decimalDate


#This should handle writing out extents (likely unused variables here)
def extentDive(mapF, q, validInodeLoc, dirEntrySynchronizers, BGSize, bSize, partitionStart, tabs, pdt):

    #for styling

    tabs += 1

    q.write("\t" * tabs)

    q.write("One level down the tree!\n\n")

    extTest = bytesToDec(mapF[validInodeLoc : validInodeLoc + 2])

    depthTree = bytesToDec(mapF[validInodeLoc + 6 : validInodeLoc + 8])


    #For testing extent and previous tree depth
    if((extTest == 62218) and (depthTree == pdt - 1)):

        q.write("\t" * tabs)
        q.write("Extent Header Information: \n")


        numExt =  bytesToDec(mapF[validInodeLoc + 2: validInodeLoc + 4])
        

        q.write("\t" * tabs)
        q.write("Number of Extents: {}\n".format(numExt))

        maxExt = bytesToDec(mapF[validInodeLoc + 4 : validInodeLoc + 6])
        
        q.write("\t" * tabs)
        q.write("Max Number of Extents: {}\n".format(maxExt))


        q.write("\t" * tabs)
        q.write("Depth of Tree: {}\n".format(depthTree))


        q.write("\t" * tabs)
        q.write("Generation ID: {}\n\n".format(bytesToDec(mapF[validInodeLoc + 8: validInodeLoc + 12])))

        q.write("\t" * tabs)
        q.write("Known extents:\n\n")

        #Get to first ext
        validInodeLoc += 12


        for i in range(numExt):

            
            #Extent index, or leaf
            if(depthTree > 0):

                q.write("\t" * tabs)
                q.write("Logical Block Number: {}\n".format(bytesToDec(mapF[validInodeLoc + i*12: validInodeLoc + 4 + i*12])))
                numBlocksInExt = bytesToDec(mapF[validInodeLoc + 4 + i*12: validInodeLoc + 6 + i*12])

                q.write("\t" * tabs)
                q.write("Number of blocks in extent: {}\n".format(numBlocksInExt))
                
                q.write("\t" * tabs)
                q.write("Depth == {}\n".format(depthTree))


                lower32bits = bytesToDec(mapF[validInodeLoc + 6 + i*12: validInodeLoc + 10 + i*12])
                higher16bits = bytesToDec(mapF[validInodeLoc + 10 + i*12: validInodeLoc + 12 + i*12])
                phyBlockLoc = (higher16bits * 4294967296) + lower32bits

                q.write("\t" * tabs)
                q.write("Physical Block Location (in blocks): {}\n\n".format(phyBlockLoc))

                extentDive(mapF, q, phyBlockLoc * bSize + partitionSTart, dirEntrySynchronizers, BGSize, bSize, partitionStart, tabs + 1, depthTree)

            else:

                q.write("\t" * tabs)
                q.write("Logical Block Number: {}\n".format(bytesToDec(mapF[validInodeLoc + i*12: validInodeLoc + 4 + i*12])))
                
                numBlocksInExt = bytesToDec(mapF[validInodeLoc + 4 + i*12: validInodeLoc + 6 + i*12])

                q.write("\t" * tabs)
                q.write("Number of blocks in extent: {}\n".format(numBlocksInExt))

                higher16bits = bytesToDec(mapF[validInodeLoc + 6 + i*12: validInodeLoc + 8 + i*12])
                lower32bits = bytesToDec(mapF[validInodeLoc + 8 + i*12: validInodeLoc + 12 + i*12])
                phyBlockLoc = (higher16bits * 4294967296) + lower32bits

                if(i==0):
                    firstDirectBlock = phyBlockLoc # Assuming the first extent is pointing to the directory entries. However, it might be multiple extents for additional directory entries
            
                q.write("\t" * tabs)
                q.write("Physical Block Location (in blocks): {}\n\n".format(phyBlockLoc))   

    else:

        q.write("\t" * tabs)
        q.write("Location did not have correct extent header magic number!\n\n")


#We currently only look at second version of inode data structure,  (name length is one byte, and filetype)
def printDirectoryInfo(mapF,q, dirEntryLoc, numBlocksInExt, extFlag, blockSize, inodeDict, fileVerDict):

    q.write("\n\n-Begin Directory Entry Output-\n\n")

    entryLen = 12 

    #count bytes to understand where ending is. 
    trackBytes = 0

    #This triggers true when some conditions have been met.
    tripBit = False
    stillMore = True


    while((entryLen !=0) and stillMore):

        inodeNum = bytesToDec(mapF[dirEntryLoc : dirEntryLoc + 4])

        entryLen = bytesToDec(mapF[dirEntryLoc + 4 : dirEntryLoc + 6])

        #This updates the entry len.
        if((entryLen != 0)):

        
            nameLength = mapF[dirEntryLoc + 6]
            fileType = mapF[dirEntryLoc + 7]
            oldDirEntryLoc = dirEntryLoc
            oldEntryLen = entryLen

            padding=0

            if(4 - (nameLength % 4 ) !=0):
                padding = 4 - (nameLength % 4 ) 
        

            #This only works if the system is correct.
            if((trackBytes % blockSize == 0) and (tripBit)):

                if(extFlag):
                    if(numBlocksInExt > 1):
                        numBlocksInExt -=1 # We have already parsed the block
                        
                        dirEntryLoc += entryLen # Go to record in next block
                        trackBytes += entryLen
                    else:
                         
                        entryLen = 0 # reached the last record in last block
                        stillMore = False
                else: 
                    entryLen = 0
                    stillMore = False
            else:

                updateOffset = entryLen 

                if((updateOffset % 4) != 0):
                    updateOffset = updateOffset + (4 - (updateOffset % 4))

                dirEntryLoc += updateOffset

                #This is just in case the next block has been overwritten, and we start reading junk.
                oldTrackBytes = trackBytes

                trackBytes += updateOffset

                #If the byte offset from one block to the next the old mod is greater than the new, 
                #it means that the transition from one block to the next wasn't on its edge.
                #This means we have likely been reading junk.
                if((trackBytes % blockSize > 0) and ((oldTrackBytes % blockSize) > (trackBytes % blockSize)) ):
                    numBlocksInExt = 0
                    entryLen = 0
                    q.write("Likely this block and the next blocks of the directory have been overwritten.")

                tripBit = True


            if(stillMore):

                q.write("Directory Entry location: {}\n".format(oldDirEntryLoc))

                if (inodeNum == 0):
                    q.write("inode Number: {} (NOT VALID)\n".format(inodeNum))

                else:
                    q.write("inode Number: {}\n".format(inodeNum))

                q.write("Length of Entry: {}\n".format(oldEntryLen))
                
                q.write("Name Length: {}\n".format(nameLength))
                
                q.write("FileType: {}\n".format(fileType))         

                filename = mapF[oldDirEntryLoc + 8 : oldDirEntryLoc + 8 + nameLength]

                q.write("Filename: {}\n\n".format(filename))

                #Update inode dictionary if we haven't seen this inode yet.
                if(inodeNum not in inodeDict):

                    inodeDict[inodeNum] = [filename]
                
    q.write("-END OF DIRECTORY ENTRIES-\n\n")



    
#May be able to be done with other function
#Primary difference his handling extent/nonextent inodes, and returns previous value, rather than none if conditions not met.
def updateDirSynch(mmapF, relativeOffsetInode, bSize, partitionStart, preValue, extFlag):


    if(extFlag):

        numExt = bytesToDec(mmapF[relativeOffsetInode + 42: relativeOffsetInode + 44])

        maxExt = bytesToDec(mmapF[relativeOffsetInode + 44: relativeOffsetInode + 46])

        depthTree = bytesToDec(mmapF[relativeOffsetInode + 46: relativeOffsetInode + 48])

        numBlocksInExt = 1

        numBlocksInExt = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 58 ])

        #Extent index, or leaf
        if(depthTree > 0):

            lower32bits = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 60 ])
            higher16bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 62 ])
            phyBlockLoc = (higher16bits * 4294967296) + lower32bits            
           
        else:
                     
            higher16bits = bytesToDec(mmapF[relativeOffsetInode + 58 : relativeOffsetInode + 60 ])
            lower32bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 64 ])
            phyBlockLoc = (higher16bits * 4294967296) + lower32bits

        dirBlockLocAdjusted = (phyBlockLoc * bSize + partitionStart ) % mmapF.size()

        inodeNum = bytesToDec(mmapF[dirBlockLocAdjusted : dirBlockLocAdjusted + 4])

        if(bytesToDec(mmapF[dirBlockLocAdjusted  + 4: dirBlockLocAdjusted  + 4 + 3]) == 65548):
            return [relativeOffsetInode, inodeNum]

    else:

        #We assume first block has all dir entryies.  
        dirBlockLoc =  bytesToDec(mmapF[relativeOffsetInode + 40 : relativeOffsetInode + 44])

        #This ensures we never read outside image
        dirBlockLocAdjusted = (dirBlockLoc*bSize + partitionStart) % mmapF.size()

        inodeNum = bytesToDec(mmapF[dirBlockLocAdjusted : dirBlockLocAdjusted + 4])
    
        if(bytesToDec(mmapF[dirBlockLocAdjusted + 4: dirBlockLocAdjusted + 4 + 3]) == 65548):
            return [relativeOffsetInode, inodeNum]

    return preValue


#This is the primary function for printing out inode information
def printInodes(mapF, q, validInodeLoc, dirEntrySynchronizers, BGSize, bSize, partitionStart, inodeDict, fileVerDict, c):


    # Estimated iNode Number, 0 means that this number has not been updated.
    estInodeNum = 0

    # Estimated File Name
    estFilename = "No filename estimation given"

    fileFlag = mapF[validInodeLoc + 1]
    fileFlag = fileFlag >> 4
    extFlag = mapF[validInodeLoc + 34]

    extFlag = ((extFlag & 0x08) == 0x08)


    #If it is a directory, we need to update our directory synchronization list.
    if(fileFlag == 0x04):
        dirEntrySynchronizers[math.floor((validInodeLoc - partitionStart)/BGSize)] = updateDirSynch(mapF, validInodeLoc, bSize, partitionStart, dirEntrySynchronizers[math.floor((validInodeLoc - partitionStart)/BGSize)], extFlag)

    #Obtaining known information
    inodeStart = dirEntrySynchronizers[math.floor((validInodeLoc - partitionStart)/BGSize)]

    offsetOff = "No issue with offset from known directory."


    #If the hit does not line up with a likely ground truth.
    if(inodeStart != None):
        if((validInodeLoc - inodeStart[0]) % 256 != 0):
            offsetOff = "THIS ENTRY IS LIKELY A FALSE POSITIVE.  NOT ALIGNED WITH KNOWN DIRECTORY"
            #We still print this, since it is possible it is a true positive.
            q.write("THIS ENTRY IS LIKELY A FALSE POSITIVE.  NOT ALIGNED WITH KNOWN DIRECTORY\n")

    #This is where all the inode info is generated
    fv = bytesToDec(mapF[validInodeLoc + 100: validInodeLoc + 104] )
    crt = bytesToDec(mapF[validInodeLoc + 144 : validInodeLoc + 148])


    #Inodes without ground truth information are less trustworthy, and will not have associated directory entry or inode number information.
    if(inodeStart != None):

        #Inode start Location should be the actual physical location
        inodeStartLoc = inodeStart[0]

        #This should be the recorded inode number
        inodeStartNum = inodeStart[1]
        if(((validInodeLoc - inodeStartLoc) % 256) == 0):

            estInodeNum = float(inodeStartNum) + ((validInodeLoc - inodeStartLoc)/256)

            q.write("Estimated iNode Number: {}\n".format(estInodeNum))

            
            #Basically, if we first encounter the correct estimate, then we
            #will have a full dictionary recording
            if(estInodeNum in inodeDict):

                estFilename = inodeDict[estInodeNum][0]

                q.write("Estimated Filename: {}\n".format(estFilename))

                if(len(inodeDict[estInodeNum]) == 1):
                    holdList = inodeDict[estInodeNum]
                
                    holdList.append(crt)
                    
                    holdList.append(fv)

                    inodeDict[estInodeNum] = holdList

                    #key fv: crt, inodenum, filename
                    fileVerDict[fv] = [crt, estInodeNum, holdList[0]] 


    rcdInodeNum = 0
    rcdFN = "Not updated!"

    #If the file version is found in our record, we output its record number.
    if(fv in fileVerDict):
        if (fileVerDict[fv][0] == crt):
            rcdInodeNum = fileVerDict[fv][1]
            q.write("Recorded inode number: {}\n".format(rcdInodeNum))


    #if we can, we always want to print the file name.    
    if(fv in fileVerDict):
        if (fileVerDict[fv][0] == crt):
            rcdFN = fileVerDict[fv][2]
            q.write("Recorded filename: {}\n".format(rcdFN))


    #Default output
    q.write("iNode Byte location (relative to start of image): {}\n".format(validInodeLoc))


    fType = "Not updated!"

    if(fileFlag == 0x04):
        fType = "DIR"
        q.write("Filetype is DIR\n")
    elif(fileFlag == 0x08):
        fType = "REGULARFILE"
        q.write("Filetype is REGULAR FILE\n")
    else:
        fType = "SYMBOLICLINK"
        q.write("Filetype is SYMBOLIC LINK\n")

    mode = mapF[validInodeLoc : validInodeLoc + 2]
    mode = bytesToDec(mode)

    #Permissions string
    permString = ""

    q.write("Permissions: ")
    for l in range(9):
        if(((mode >> (8 - l)) & 0x0001) != 1):
            permString += "-"
            q.write("-")
        else:
            if((l == 0) or (l==3) or (l==6)):
                permString += "r"
                q.write("r")
            elif((l == 1) or (l==4) or (l==7)):
                permString += "w"
                q.write("w")
            else:
                permString += "x"
                q.write("x")

    q.write("\n")

    userID = bytesToDec(mapF[validInodeLoc + 2: validInodeLoc + 4])

    q.write("User ID: {}\n".format(userID))

    lower32Size = bytesToDec(mapF[validInodeLoc + 4: validInodeLoc + 8])
    upper32Size = bytesToDec(mapF[validInodeLoc + 108: validInodeLoc + 112])
    totSize = (upper32Size * 4294967296) + lower32Size

    q.write("Total Size: {}\n".format(totSize))

    sectorCount = bytesToDec(mapF[validInodeLoc + 28: validInodeLoc + 32])

    q.write("Sector Count: {}\n".format(sectorCount))

    accessed = bytesToDec(mapF[validInodeLoc + 8 : validInodeLoc + 12])

    nsA = bytesToDec(mapF[validInodeLoc + 140 : validInodeLoc + 144]) >> 2


    ATDT = datetime.datetime.utcfromtimestamp(accessed).strftime('%Y-%m-%d %H:%M:%S')

    q.write("Last Accessed: {} and {} ns\n".format(ATDT, nsA))



    changed = bytesToDec(mapF[validInodeLoc + 12 : validInodeLoc + 16])

    nsC = bytesToDec(mapF[validInodeLoc + 132 : validInodeLoc + 136]) >> 2

    CTDT = datetime.datetime.utcfromtimestamp(changed).strftime('%Y-%m-%d %H:%M:%S')

    q.write("Last Changed Date: {} and {} ns\n".format(CTDT, nsC))



    
    modified = bytesToDec(mapF[validInodeLoc + 16 : validInodeLoc + 20]) 

    nsM = bytesToDec(mapF[validInodeLoc + 136 : validInodeLoc + 140]) >> 2

    MTDT = datetime.datetime.utcfromtimestamp(modified).strftime('%Y-%m-%d %H:%M:%S')

    q.write("Last Modified: {} and {} ns\n".format(MTDT, nsM))



    deleted = bytesToDec(mapF[validInodeLoc + 20 : validInodeLoc + 24])
    DTDT = datetime.datetime.utcfromtimestamp(deleted).strftime('%Y-%m-%d %H:%M:%S')

    if(deleted == 0):
        q.write("Date Deleted: Not Applicable\n")
    else:
        q.write("Date Deleted: {}\n".format(DTDT))

    createdTime = bytesToDec(mapF[validInodeLoc + 144 : validInodeLoc + 148])
    nsCr = bytesToDec(mapF[validInodeLoc + 148 : validInodeLoc + 152]) >> 2

    CRTDT = datetime.datetime.utcfromtimestamp(createdTime).strftime('%Y-%m-%d %H:%M:%S')
    q.write("Created Date: {} and {} ns\n".format(CRTDT, nsCr))



    fileVer = bytesToDec(mapF[validInodeLoc + 100: validInodeLoc + 104] )


    q.write("File Version: {}\n".format(fileVer))

    gID = bytesToDec(mapF[validInodeLoc + 24: validInodeLoc + 26])

    q.write("Group ID: {}\n".format(gID))

    linkCount = bytesToDec(mapF[validInodeLoc + 26: validInodeLoc + 28])

    q.write("Link Count: {}\n".format(linkCount))


    #Dealing with extents/block pointers
    numBlocksInExt = 1

    firstDirectBlock = 0

    #Meant for the csv.
    dataPtrs = ""


    if(extFlag):

        q.write("\nExtent Header Information: \n")

        dataPtrs += "Extent Header Information | "

        numExt = bytesToDec(mapF[validInodeLoc + 42: validInodeLoc + 44])

        dataPtrs += "Number of Extents: "

        dataPtrs += str(numExt)

        q.write("Number of Extents: {}\n".format(numExt))

        dataPtrs += " | Number of Extents: "

        maxExt = bytesToDec(mapF[validInodeLoc + 44: validInodeLoc + 46])
        q.write("Max Number of Extents: {}\n".format(maxExt))

        dataPtrs += str(maxExt)

        depthTree = bytesToDec(mapF[validInodeLoc + 46: validInodeLoc + 48])
        q.write("Depth of Tree: {}\n".format(depthTree))

        dataPtrs += " | Depth of Tree: "
        dataPtrs += str(depthTree)

        q.write("Generation ID: {}\n\nKnown extents:\n\n".format(bytesToDec(mapF[validInodeLoc + 48: validInodeLoc + 52])))

        dataPtrs += " | Generation ID: "

        dataPtrs += str(bytesToDec(mapF[validInodeLoc + 48: validInodeLoc + 52]))

        dataPtrs += " | Known extents in .txt file"


        #Physical block location is raw data.  That is, it is the block in the partition in which the extent is stored.
        for i in range(numExt):

            #Extent index, or leaf
            if(depthTree > 0):
                q.write("Logical Block Number: {}\n".format(bytesToDec(mapF[validInodeLoc + 52 + i*12: validInodeLoc + 56 + i*12])))
                numBlocksInExt = bytesToDec(mapF[validInodeLoc + 56 + i*12: validInodeLoc + 58 + i*12])
                q.write("Number of blocks in extent: {}\n".format(numBlocksInExt))
                q.write("Depth == {}\n".format(depthTree))

                lower32bits = bytesToDec(mapF[validInodeLoc + 56 + i*12: validInodeLoc + 60 + i*12])
                higher16bits = bytesToDec(mapF[validInodeLoc + 60 + i*12: validInodeLoc + 62 + i*12])
                phyBlockLoc = (higher16bits * 4294967296) + lower32bits
                
                if(i==0):
                    firstDirectBlock = phyBlockLoc # Assuming the first extent is pointing to the directory entries. However, it might be multiple extents for additional directory entries
                
                q.write("Physical Block Location (in blocks): {}\n\n".format(phyBlockLoc))

                extentDive(mapF, q, phyBlockLoc * bSize + partitionStart, dirEntrySynchronizers, BGSize, bSize, partitionStart, 0, depthTree)

            else:
                q.write("Logical Block Number: {}\n".format(bytesToDec(mapF[validInodeLoc + 52 + i*12: validInodeLoc + 56 + i*12])))
                numBlocksInExt = bytesToDec(mapF[validInodeLoc + 56 + i*12: validInodeLoc + 58 + i*12])
                q.write("Number of blocks in extent: {}\n".format(numBlocksInExt))

                

                higher16bits = bytesToDec(mapF[validInodeLoc + 58 + i*12: validInodeLoc + 60 + i*12])
                lower32bits = bytesToDec(mapF[validInodeLoc + 60 + i*12: validInodeLoc + 64 + i*12])
                phyBlockLoc = (higher16bits * 4294967296) + lower32bits
                
                if(i==0):
                    firstDirectBlock = phyBlockLoc # Assuming the first extent is pointing to the directory entries. However, it might be multiple extents for additional directory entries
                

                q.write("Physical Block Location (in blocks): {}\n\n".format(phyBlockLoc))         


    #Outputting block pointers.
    else:

        q.write("\nDirect Block Pointers (In Blocks): \n")


        dataPtrs += "Direct Block Pointers (In Blocks): "    


        if(deleted == 0):

            firstDirectBlock = bytesToDec(mapF[validInodeLoc + 40: validInodeLoc + 44])

            dataPtrs += "First Direct block: "

            dataPtrs += str(firstDirectBlock)

            for l in range(12):
                q.write("{} ".format(bytesToDec(mapF[validInodeLoc + 40 + l*4: validInodeLoc + 40 + 4 + l*4])))

            q.write("\nSingle Indirect Block Pointer: {}\n".format(bytesToDec(mapF[validInodeLoc + 88: validInodeLoc + 92])))

            q.write("Double Indirect Block Pointer: {}\n".format(bytesToDec(mapF[validInodeLoc + 92: validInodeLoc + 96])))

            q.write("Triple Indirect Block Pointer: {}\n\n".format(bytesToDec(mapF[validInodeLoc + 96: validInodeLoc + 100])))
        else:

            q.write("File was deleted.  Pointers wiped.\n\n")



    if((fileFlag == 0x04)):

        if(deleted != 0):
            q.write("Directory entries cannot be retrieved\n\n")
        
        #If both directory checks fail, we say that this dir was likely overwritten.
        elif((dir4CheckValidNonExt(mapF, validInodeLoc, BGSize, bSize, partitionStart) or dir4CheckValidExt(mapF, validInodeLoc, BGSize, bSize, partitionStart)) == False):
            q.write("Directory entry is likely overwritten, or this is a false positive.\n\n")


        else:
            #For both extent and non-extent inodes, we have a limitation that we only check their first extent/block listed.
            #Current limitation.
            dirEntryLoc = firstDirectBlock * bSize + partitionStart
            printDirectoryInfo(mapF,q, dirEntryLoc, numBlocksInExt, extFlag, bSize, inodeDict, fileVerDict)

    #End of inode (txt file)
    q.write("***************************************************************************************\n\n")

    #Writing out csv
    c.writerow([validInodeLoc, estInodeNum, estFilename,rcdInodeNum,rcdFN, fType, permString, userID, totSize, sectorCount, ATDT,nsA, CTDT,nsC, MTDT, nsM, DTDT, CRTDT, nsCr, fileVer, gID, linkCount, dataPtrs,offsetOff])



#Same as print inode method, except only for updating dictionary.
def updateInodeDict(mapF, dirEntryLoc, numBlocksInExt, blockSize, inodeDict, fileVerDict, extFlag):

    entryLen = 12 

    #count bytes to understand where ending is. 
    trackBytes = 0

    tripBit = False
    stillMore = True


    while((entryLen !=0) and stillMore):

        inodeNum = bytesToDec(mapF[dirEntryLoc : dirEntryLoc + 4])

        entryLen = bytesToDec(mapF[dirEntryLoc + 4 : dirEntryLoc + 6])

        #This updates the entry len.
        if((entryLen != 0)):

        
            nameLength = mapF[dirEntryLoc + 6]
            fileType = mapF[dirEntryLoc + 7]
            oldDirEntryLoc = dirEntryLoc
            oldEntryLen = entryLen
            padding=0

            if(4 - (nameLength % 4 ) !=0):
                padding = 4 - (nameLength % 4 ) 

            #This only works if the system is correct.
            if((trackBytes % blockSize == 0) and (tripBit)):

                if(extFlag):
                    if(numBlocksInExt > 1):
                        numBlocksInExt -=1 # We have already parsed the block
                        
                        dirEntryLoc += entryLen # Go to record in next block
                        trackBytes += entryLen
                    else:
                         
                        entryLen = 0 # reached the last record in last block
                        stillMore = False
                else: 
                    entryLen = 0
                    stillMore = False
            else:

                updateOffset = entryLen 

                if((updateOffset % 4) != 0):
                    updateOffset = updateOffset + (4 - (updateOffset % 4))

                dirEntryLoc += updateOffset

                #This is just in case the next block has been overwritten, and we start reading junk.
                oldTrackBytes = trackBytes

                trackBytes += updateOffset

                #If the byte offset from one block to the next the old mod is greater than the new, 
                #it means that the transition from one block to the next wasn't on its edge.
                #This means we have likely been reading junk.
                if((trackBytes % blockSize > 0) and ((oldTrackBytes % blockSize) > (trackBytes % blockSize)) ):
                    numBlocksInExt = 0
                    entryLen - 0
                    print("Potentially bad inodes added to dictionary,")
 

                tripBit = True

            if(stillMore):

                filename = mapF[oldDirEntryLoc + 8 : oldDirEntryLoc + 8 + nameLength]

                if(inodeNum not in inodeDict):

                    inodeDict[inodeNum] = [filename]
                







#Testing directories for non-extent inodes.
def dir4CheckValidNonExt(mmapF, relativeOffsetInode, BGSize, bSize, partitionStart):

    dirBlockLoc =  bytesToDec(mmapF[relativeOffsetInode + 40  : relativeOffsetInode + 44 ])

    dirBlockLocAdjusted = (dirBlockLoc*bSize + partitionStart) % mmapF.size()

    if(bytesToDec(mmapF[dirBlockLocAdjusted + 4: dirBlockLocAdjusted + 4 + 3]) == 65548):
        return True
    else:
        return False






#Pretty much the same as the other method.  But we return/true false (only for EXT).
def dir4CheckValidExt(mmapF, relativeOffsetInode, BGSize, bSize, partitionStart):
    
    numExt = bytesToDec(mmapF[relativeOffsetInode + 42: relativeOffsetInode + 44])

    maxExt = bytesToDec(mmapF[relativeOffsetInode + 44: relativeOffsetInode + 46])

    depthTree = bytesToDec(mmapF[relativeOffsetInode + 46: relativeOffsetInode + 48])


    numBlocksInExt = 1

    numBlocksInExt = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 58 ])


    #Extent index, or leaf
    if(depthTree > 0):

        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 60 ])
        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 62 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits            

    else:

        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 58 : relativeOffsetInode + 60 ])
        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 64 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits


    dirBlockLocAdjusted = (phyBlockLoc * bSize + partitionStart ) % mmapF.size()

    if(bytesToDec(mmapF[dirBlockLocAdjusted  + 4: dirBlockLocAdjusted  + 4 + 3]) == 65548):
        return True

    return False


#Updating inode dictionary if it is not an extent directory
def dir4NonExtUpdateDict(mmapF, relativeOffsetInode, BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag):

    numBlocksInExt = 0

    dirBlockLoc =  bytesToDec(mmapF[relativeOffsetInode + 40  : relativeOffsetInode + 44 ])

    dirBlockLocAdjusted = (dirBlockLoc*bSize + partitionStart) % mmapF.size()

    if(bytesToDec(mmapF[dirBlockLocAdjusted + 4: dirBlockLocAdjusted + 4 + 3]) == 65548):
        updateInodeDict(mmapF, dirBlockLocAdjusted, numBlocksInExt, bSize, inodeDict, fileVerDict, extFlag)


#We return a short list here (inode location, inode number)
def dir4ExtUpdateDict(mmapF, relativeOffsetInode, BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag):

    numExt = bytesToDec(mmapF[relativeOffsetInode + 42: relativeOffsetInode + 44])

    maxExt = bytesToDec(mmapF[relativeOffsetInode + 44: relativeOffsetInode + 46])

    depthTree = bytesToDec(mmapF[relativeOffsetInode + 46: relativeOffsetInode + 48])

    numBlocksInExt = 1

    phyBlockLoc = 0
    dirBlockLocAdjusted = 0
    numBlocksInExt = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 58])

    #Extent index, or leaf
    if(depthTree > 0):

        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 60 ])
        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 62 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits            


    else:

        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 58 : relativeOffsetInode + 60 ])
        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 64 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits

    dirBlockLocAdjusted = (phyBlockLoc * bSize + partitionStart ) % mmapF.size()

    if(bytesToDec(mmapF[dirBlockLocAdjusted  + 4: dirBlockLocAdjusted  + 4 + 3]) == 65548):
        updateInodeDict(mmapF, dirBlockLocAdjusted, numBlocksInExt, bSize, inodeDict, fileVerDict, extFlag)



#We return a short list here (inode location, inode number)
def dir4(mmapF, relativeOffsetInode, BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag):

    numExt = bytesToDec(mmapF[relativeOffsetInode + 42: relativeOffsetInode + 44])

    maxExt = bytesToDec(mmapF[relativeOffsetInode + 44: relativeOffsetInode + 46])

    depthTree = bytesToDec(mmapF[relativeOffsetInode + 46: relativeOffsetInode + 48])

    numBlocksInExt = 1


    phyBlockLoc = 0
    dirBlockLocAdjusted = 0
    numBlocksInExt = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 58])
        

    #Extent index, or leaf
    if(depthTree > 0):

        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 56 : relativeOffsetInode + 60 ])
        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 62 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits            


    else:

        higher16bits = bytesToDec(mmapF[relativeOffsetInode + 58 : relativeOffsetInode + 60 ])
        lower32bits = bytesToDec(mmapF[relativeOffsetInode + 60 : relativeOffsetInode + 64 ])
        phyBlockLoc = (higher16bits * 4294967296) + lower32bits


    dirBlockLocAdjusted = (phyBlockLoc * bSize + partitionStart ) % mmapF.size()

    inodeNum = bytesToDec(mmapF[dirBlockLocAdjusted : dirBlockLocAdjusted + 4])


    if(bytesToDec(mmapF[dirBlockLocAdjusted  + 4: dirBlockLocAdjusted  + 4 + 3]) == 65548):
        return [relativeOffsetInode, inodeNum]

    return None




#ext4 validation
#Basically, this list updates the valid timestamp list and the directry Entry Syncrhonizer.  
def file4Validator(mmapF, relativeOffsetTS, BGSize, bSize, partitionStart, pFFShift, extFlag, magicNum, potentialUnusedZeros, validTimestamps, dirEntrySynchs, inodeDict, fileVerDict):


    #To update lists, we need to make sure that the expected extent/non-extent structures exist
    if( (((extFlag & 0x08) == 0x08)  and    (magicNum == 62218)) or (((extFlag & 0x08) != 0x08) and ((bytesToDec(potentialUnusedZeros)) == 0)) ):


        #Obtaining size as well.
        lower32Size = bytesToDec(mmapF[relativeOffsetTS + 4: relativeOffsetTS + 8])
        upper32Size = bytesToDec(mmapF[relativeOffsetTS + 108: relativeOffsetTS + 112])
        totSize = (upper32Size * 4294967296) + lower32Size

        sectorCount = bytesToDec(mmapF[relativeOffsetTS + 28: relativeOffsetTS + 32])


        #Checks to see if sector (512 bytes) count matches file size 
        if((math.ceil(totSize/bSize)) != (sectorCount/8)):
            return 0



        #Creation time, not changetime. 
        createdTime = bytesToDec(mmapF[relativeOffsetTS + 144 : relativeOffsetTS + 148])
        modified = bytesToDec(mmapF[relativeOffsetTS + 16 : relativeOffsetTS + 20]) 
        deleted = bytesToDec(mmapF[relativeOffsetTS + 20 : relativeOffsetTS + 24])



        #Is the filesize less than the image?  Do the timestamps make sense?
        if((totSize <= mmapF.size())  and ( (deleted == 0) or ((deleted >= modified) and (deleted >= createdTime)))):


            #Validating non-extent supporting inodes
            if(   ((extFlag & 0x08) != 0x08)   and (deleted == 0)):

                #We try to reduce false positives by analyzing block pointers, and what is possible.
                #Ensure no duplicate pointers

                duplicates = False

                blkPtrs = set()
                for i in range(15):
                    blkValue = bytesToDec(mmapF[relativeOffsetTS + i*4: relativeOffsetTS + i*4 + 4])

                    if(blkValue in blkPtrs):
                        duplicates = True
                    else:
                        blkPtrs.add(blkValue)

                if(not duplicates):
                    validTimestamps.append(relativeOffsetTS)



            #Right now, always adding based on the above check.
            else:
                validTimestamps.append(relativeOffsetTS)


        #Every encounter with the dictionary should update it.
        if ((pFFShift == 0x04) and (deleted == 0)):

            if ((extFlag & 0x08) == 0x08):
                dir4ExtUpdateDict(mmapF, relativeOffsetTS , BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag)
            else:
                dir4NonExtUpdateDict(mmapF, relativeOffsetTS , BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag)


        #This is for updating the dirEntrySynchs.  The point is that we may encounter times when we see inodes, but not a directory entry.
        #Therefore, we have no knowledge of its inode number.  If we collect nearby inode numbers from directories (per block group),
        #we can make an educated guess of a nearby inode's iNumber.

        #It is only updated if an entry does not exist, it is a directory, and it has not been deleted.
        #We need to test how robust this is.  This should only happen once per block group (for first pass). 
        if ((dirEntrySynchs[math.floor((relativeOffsetTS - partitionStart)/BGSize)] == None) and (pFFShift == 0x04) and (deleted == 0)):


            #Obtaining the block group index
            estBlkGrp = math.floor((relativeOffsetTS - partitionStart)/BGSize)
            testInodeNum = None

            #Different scenarios for extent support or not.
            #We are essentially obtaining the directory's inode's physical position, and inode number
            if((extFlag & 0x08) == 0x08):

                testInodeNum = dir4(mmapF, relativeOffsetTS , BGSize, bSize, partitionStart, inodeDict, fileVerDict, extFlag)

            else:


                dirBlockLoc =  bytesToDec(mmapF[relativeOffsetTS + 40 : relativeOffsetTS + 44 ])

                dirBlockLocAdjusted = (dirBlockLoc*bSize + partitionStart) % mmapF.size()  # We apply modulus to prevent accidental reading outside of list.

                inodeNum = bytesToDec(mmapF[dirBlockLocAdjusted : dirBlockLocAdjusted + 4])
                

                #non-extent
                if(bytesToDec(mmapF[dirBlockLocAdjusted + 4: dirBlockLocAdjusted + 4 + 3]) == 65548):

                    testInodeNum = [relativeOffsetTS, inodeNum]


            dirEntrySynchs[estBlkGrp] = testInodeNum


#This is the entrypoint of the validator.  Offsets from the timestamps are checked here.
#mapF, timeList, extVer, BGSize, blockGroupTotal, bSize, partitionStart
def ExtInodeValidator(mmapF, timeList, BGSize, blockGroupTotal, bSize, partitionStart, inodeDict, fileVerDict):


    #Make valid timestamp list
    validTimestamps = []
    #Make directory entry synchronization list
    dirEntrySynchs = [None] * blockGroupTotal


    for relativeOffsetTS in timeList:

        decimalDate = bytesToDec(mmapF[relativeOffsetTS: relativeOffsetTS + 4])


        #Three possible locations based on 1st, second, or third timestamp being the trigger.
        potentialFileFlag1 = mmapF[relativeOffsetTS - 7]
        potentialFileFlag2 = mmapF[relativeOffsetTS - 11]
        potentialFileFlag3 = mmapF[relativeOffsetTS - 15]

        #just shift once.  This is for obtaining the correct nibble.
        pFF1Shift = potentialFileFlag1 >> 4
        pFF2Shift = potentialFileFlag2 >> 4
        pFF3Shift = potentialFileFlag3 >> 4

        #Check for unused bytes (non-extent)
        potentialUnusedZeros1 = mmapF[relativeOffsetTS + 28:relativeOffsetTS + 32]
        potentialUnusedZeros2 = mmapF[relativeOffsetTS + 24:relativeOffsetTS + 28]
        potentialUnusedZeros3 = mmapF[relativeOffsetTS + 20:relativeOffsetTS + 24]


        #ext4 extent flag
        #ext4 magic numbers
        extFlag1 = mmapF[relativeOffsetTS + 26]
        extFlag2 = mmapF[relativeOffsetTS + 22]
        extFlag3 = mmapF[relativeOffsetTS + 18]


        #ext4 magic numbers
        magicNum1 = bytesToDec(mmapF[relativeOffsetTS + 32:relativeOffsetTS + 34])
        magicNum2 = bytesToDec(mmapF[relativeOffsetTS + 28:relativeOffsetTS + 30])
        magicNum3 = bytesToDec(mmapF[relativeOffsetTS + 24:relativeOffsetTS + 26])


        #x08 is Regular File, 0x04 is directory, 0x0A is Symbolic Links.

        #Basically, check if first offset is one of the flags we care about.
        #Currently, we allow for multiple inode start possibilities.  (may change in future)
        if(((pFF1Shift & 0xff) == 0x08) or ((pFF1Shift & 0xff) == 0x04) or ((pFF1Shift & 0xff) == 0x0A)):


            file4Validator(mmapF, relativeOffsetTS - 8, BGSize, bSize, partitionStart, pFF1Shift, extFlag1, magicNum1, potentialUnusedZeros1, validTimestamps, dirEntrySynchs, inodeDict, fileVerDict)



        if(((pFF2Shift & 0xff) == 0x08) or ((pFF2Shift & 0xff) == 0x04) or ((pFF2Shift & 0xff) == 0x0A)):

            file4Validator(mmapF, relativeOffsetTS - 12, BGSize, bSize, partitionStart, pFF2Shift, extFlag2, magicNum2, potentialUnusedZeros2, validTimestamps, dirEntrySynchs, inodeDict, fileVerDict)




        if(((pFF3Shift & 0xff) == 0x08) or ((pFF3Shift & 0xff) == 0x04) or ((pFF3Shift  & 0xff) == 0x0A)):


            file4Validator(mmapF, relativeOffsetTS - 16, BGSize, bSize, partitionStart, pFF3Shift, extFlag3, magicNum3, potentialUnusedZeros3, validTimestamps, dirEntrySynchs, inodeDict, fileVerDict)


    #We must return these values
    return validTimestamps, dirEntrySynchs



#Main function.  Essentially performs full pass of image collecting directory information and validtimestamp location information.  The second pass prints out inode information.
#Timestamp Location, .dd file location, partition start (still necessary?), extVersion, ramSwtich (maybe not, since memory mapping should take care of it)
def main(timestamps, fileLoc, partitionStart, bSize):

    #Start of partition
    partitionStart = int(partitionStart)

    #Size of assumed timestamp
    bSize = int(bSize)

    #We always assume block group size is 8 times greater than block size.
    BGSize = bSize * (bSize*8)

    q = open("ExtResults.txt", "w")
    
    c = csv.writer(open("ExtResults.csv", 'w', newline=''))

    #Adding column headers
    c.writerow(["Valid Inode Location", "Estimated Inode Number", "Estimated Filename", "Recorded Inode Number", "Recorded Filename", "Filetype", "Permissions", "User ID", "Total Size", "Sector Count", "Access Time", "Access Time ns", "Change Time", "Change Time ns", "Modified Time", "Modified Time ns", "Deleted Time", "Created Time", "Created Time ns", "File Version", "Group ID", "Link Count", "Data Pointers/Extents", "Is Inode offset off?"])


    #Read in list of timestamps, turn it into a list of ints
    timeList = [int(line.rstrip('\n')) for line in open(timestamps)]
    
    f = open(fileLoc, "rb+")

    #Getting mmap of file
    mapF = mmap.mmap(f.fileno(), 0)

    fileSize = mapF.size()

    #Estimating block group total
    #At least this many
    blockGroupTotal = math.ceil((int(fileSize) - partitionStart)/int(BGSize))


    #This is a dictionary that collections inode numbers and filenames from directories.
    inodeDict = {}

    #This is a dictionary that adds file version and creation time to the above dictionary, except it is keyed with the fileversion.
    fileVerDict = {}



    #We are getting list of valid inodes (can be improved), as well as first directory for each blockgroup 
    validInodes, dirEntrySynchronizers = ExtInodeValidator(mapF, timeList, BGSize, blockGroupTotal, bSize, partitionStart, inodeDict, fileVerDict)


    #For each of the valid inodes, we need to output their information (including directory entries)
    for i in validInodes:
        printInodes(mapF, q, i, dirEntrySynchronizers, BGSize, bSize, partitionStart, inodeDict, fileVerDict, c)

    q.close()
    mapF.close()

#For commandline functionality
def parse_arguments():
    parser = argparse.ArgumentParser(description='This program is intended to identify potential timestamps from fairly general filesystem metadata structures.  It does so by looking for closely co-located and repetitive strings of bytes within a raw disk image.')
    parser.add_argument("timeFilePath", help = "Location of timestamps.")
    parser.add_argument("imagePath", help ="Location of image or dump.")
    parser.add_argument("readStart", help ="Byte position processing begins at.")
    parser.add_argument("blockSize", help ="Assumed Size of Ext block")

    return parser.parse_args()



if __name__ == '__main__':


    arguments = parse_arguments()


    main(arguments.timeFilePath, arguments.imagePath, arguments.readStart, arguments.blockSize) 

    
