import base64
import bitstring
import re
from time import time, sleep
from queue import Queue
import logging

# TODO
# apply checkForResponse to User Data Buffer
# implement sending Userdata
# implement rreq buffer with timeout 
# implement startup/reboot sequence
# hasEntryForDestination also returns true on invalid routes, check if thats ok
# Userdata encoding not working
"""
Traceback (most recent call last):
  File "C:\Schule\Studium\5.Semester\TMS\Code\SerielleKommunikation\Communicator.py", line 60, in <module>
    MainPrompt().cmdloop()
  File "C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.10_3.10.2544.0_x64__qbz5n2kfra8p0\lib\cmd.py", line 138, in cmdloop
    stop = self.onecmd(line)
  File "C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.10_3.10.2544.0_x64__qbz5n2kfra8p0\lib\cmd.py", line 217, in onecmd
    return func(arg)
  File "C:\Schule\Studium\5.Semester\TMS\Code\SerielleKommunikation\Communicator.py", line 38, in do_send
    self.client.send(adress,msg)
  File "C:\Schule\Studium\5.Semester\TMS\Code\SerielleKommunikation\SerComClient.py", line 20, in send
    self.protocoll.sendUserData(destinaion,msg)
  File "C:\Schule\Studium\5.Semester\TMS\Code\SerielleKommunikation\AODV.py", line 268, in sendUserData
    self.send(self.routingTable.getEntry(destination).nextHop,userData.encode())
  File "C:\Schule\Studium\5.Semester\TMS\Code\SerielleKommunikation\AODV.py", line 52, in encode
    udbin = bitstring.BitArray(bytes=self.userData.encode("utf-8"))
AttributeError: 'bytes' object has no attribute 'encode'. Did you mean: 'decode'?
"""

logging.basicConfig(level=logging.DEBUG)

class Route:
    destinationAdress = ""
    destinationSequenceNumber = 0
    isDestinationSequenceNumberValid = False
    hopCount = 0
    nextHop = ""
    precursers = []
    lifetime = 0
    active = False

class UserData:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.type = 0
        self.destinationAdress = ""
        self.userData = ""
        self.numRetries = 0

        self.format = "uint6=type, hex16=destinationAdress"
        self.unpackformat = self.format + ", bits=userData"

    def decode(self, msg: str):
        base64_bytes = msg.encode("utf-8")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        arglist = byteArray.unpack(self.unpackformat)
        print(arglist)
        self.type = arglist[0]
        self.destinationAdress = arglist[1]
        self.userData = arglist[2].tobytes().decode("utf-8")
    
    def encode(self):
        byteArray = bitstring.pack(self.format, **self.__dict__)
        udbin = bitstring.BitArray(bytes=self.userData.encode("utf-8"))
        byteArray.append(udbin)
        base64string = base64.b64encode(byteArray.tobytes())
        return base64string.decode("utf-8")

class RouteRequest:
    def __init__(self) -> None:
        self.type = 1      
        self.unknownSequenceNumber = False
        self.flagTwo = False
        self.flagThree = False
        self.flagFour = False
        self.flagFive = False
        self.flagSix = False
        self.hopCount = 0
        self.requestID = 0
        self.destinationAdress = "000F"
        self.destinationSequence = 0
        self.originatorAdress = "000F"
        self.originatorSequence = 0
        self.format = "uint6=type, bool1=unknownSequenceNumber, bool1=flagTwo, bool1=flagThree, bool1=flagFour, bool1=flagFive, bool1=flagSix, uint6=hopCount, uint6=requestID, hex16=destinationAdress, uint8=destinationSequence, hex16=originatorAdress, uint8=originatorSequence"

        self.logger = logging.getLogger(__name__)
        self.previousHop = ""

    def decode(self, msg: str):
        base64_bytes = msg.encode("utf-8")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        arglist = byteArray.unpack(self.format)
        self.type = arglist[0]
        self.unknownSequenceNumber = arglist[1]
        self.flagTwo = arglist[2]
        self.flagThree = arglist[3]
        self.flagFour = arglist[4]
        self.flagFive = arglist[5]
        self.flagSix = arglist[6]
        self.hopCount = arglist[7]
        self.requestID = arglist[8]
        self.destinationAdress = arglist[9]
        self.destinationSequence = arglist[10]
        self.originatorAdress = arglist[11]
        self.originatorSequence = arglist[12]
    
    def encode(self):
        byteArray = bitstring.pack(self.format, **self.__dict__)
        base64string = base64.b64encode(byteArray.tobytes())
        return base64string.decode("utf-8")

    def incrementHopCount(self):
        self.hopCount +=1
        self.hopCount = self.hopCount % 63

class RouteReply:
    def __init__(self) -> None:
        self.type = 2
        self.lifetime = None
        self.destinationAdress = None
        self.destinationSequence = None
        self.originatorAdress = None
        self.hopCount = 0
        self.format = "uint6=type, uint18=lifetime, hex16=destinationAdress, uint8=destinationSequence, hex16=originatorAdress, uint8=hopCount"
        
        self.previousHop = ""

    def decode(self, msg: str):
        base64_bytes = msg.encode("utf-8")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        arglist = byteArray.unpack(self.format)
        self.type = arglist[0]
        self.lifetime = arglist[1]
        self.destinationAdress = arglist[2]
        self.destinationSequence = arglist[3]
        self.originatorAdress = arglist[4]
        self.hopCount = arglist[5]

    def encode(self):
        print(self.__dict__)
        byteArray = bitstring.pack(self.format, **self.__dict__)
        base64string = base64.b64encode(byteArray.tobytes())
        return base64string.decode("utf-8")
    
    def incrementHopCount(self):
        self.hopCount +=1
        self.hopCount = self.hopCount % 63

class RoutingTable:
    table = {}
    logger = logging.getLogger(__name__)

    def uintToInt(self, int: int):
        intbit = bitstring.BitArray(uint=int, length = 8)
        return intbit.int

    def isUpdatedNeeded(self,currentEntry: Route, newEntry: Route) -> bool:
        newDestSeqNum = self.uintToInt(newEntry.destinationSequenceNumber)
        currentDestSeqNum = self.uintToInt(currentEntry.destinationSequenceNumber)

        differenceWithOverflow = newDestSeqNum-currentDestSeqNum
        if differenceWithOverflow < 127:
            differenceWithOverflow = differenceWithOverflow % 127 - 127

        if not newEntry.isDestinationSequenceNumberValid:
            return True
        if differenceWithOverflow < 0:
            return True
        if currentDestSeqNum == newDestSeqNum and newEntry.hopCount < currentEntry.hopCount:
            return True

    def hasEntryForDestination(self, destination: str) -> bool:
        return self.table.get(destination) != None

    def getEntry(self, destination: str) -> Route:
        return self.table.get(destination)

    def updateEntryWithDestination(self,destinationAdress: str):
        if not self.hasEntryForDestination(destinationAdress):
            self.logger.debug("Updating Route to "+destinationAdress)
            newRoute = Route()
            newRoute.isDestinationSequenceNumberValid = False
            newRoute.destinationSequenceNumber = 0
            newRoute.destinationAdress = destinationAdress
            newRoute.lifetime = int(time()*1000)+AODV.ACTIVE_ROUTE_TIMEOUT 
            newRoute.hopCount = 1
            newRoute.nextHop = destinationAdress
            newRoute.active = True
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntryWithRREP(self, rrep: RouteReply):
        self.logger.debug("Updating Route to "+rrep.destinationAdress)
        newRoute = Route()
        newRoute.isDestinationSequenceNumberValid = True
        newRoute.destinationSequenceNumber = rrep.destinationSequence
        newRoute.destinationAdress = rrep.destinationAdress
        newRoute.lifetime = int(time()*1000)+rrep.lifetime
        newRoute.nextHop = rrep.previousHop
        newRoute.active = True
        oldRoute = self.getEntry(rrep.destinationAdress)
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntryWithRREQ(self, rreq: RouteRequest):
        self.logger.debug("Updating Route to "+rreq.originatorAdress)
        oldRoute = self.getEntry(rreq.originatorAdress)
        currentLifetime = 0
        currentDesitantionSecquenceNumber = 0
        if oldRoute is not None:
            currentLifetime = oldRoute.lifetime
            currentDesitantionSecquenceNumber = oldRoute.destinationSequenceNumber
        newRoute = Route()
        newRoute.isDestinationSequenceNumberValid = True
        newRoute.destinationSequenceNumber = max(currentDesitantionSecquenceNumber,rreq.originatorSequence)
        newRoute.destinationAdress = rreq.originatorAdress
        newRoute.lifetime = max(currentLifetime, int(time()*1000)+ 2*AODV.NET_TRAVERSAL_TIME - 2*rreq.hopCount* AODV.NODE_TRAVERSAL_TIME)
        newRoute.nextHop = rreq.previousHop
        newRoute.hopCount = rreq.hopCount
        newRoute.active = True
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntry(self, route: Route):
        self.table.update({route.destinationAdress : route})

class AODV:
    def __init__(self, outputQueue: Queue):
        self.outputQueue = outputQueue
        self.routingTable = RoutingTable()
        self.reverseRoutingTable = RoutingTable()
        self.ownAdress = None
        self.sequenceNumber = 0
        self.requestID = 0
        self.rreqBuffer = []
        self.userDataBuffer = []
        self.logger = logging.getLogger(__name__)

        self.ACTIVE_ROUTE_TIMEOUT = int(3000)
        self.NODE_TRAVERSAL_TIME = int(40)
        self.MY_ROUTE_TIMEOUT = 2 * self.ACTIVE_ROUTE_TIMEOUT
        self.NET_TRAVERSAL_TIME =2 * self.NODE_TRAVERSAL_TIME # * NET_DIAMETER
        self.PATH_DISCOVERY_TIME = 2 * self.NET_TRAVERSAL_TIME
        self.RREQ_RETRIES = int(2)

    def incrementSequenceNumber(self):
        self.sequenceNumber += 1
        self.sequenceNumber = self.sequenceNumber % 255

    def decrementSequenceNumber(self):
        self.sequenceNumber -= 1
        self.sequenceNumber = self.sequenceNumber % 255

    def incrementRequestID(self):
        self.requestID += 1
        self.requestID = self.requestID % 63

    def processRREQ(self, rreq: RouteRequest):
        self.logger.debug(rreq.__dict__)
        self.routingTable.updateEntryWithDestination(rreq.previousHop)
        for entry in self.rreqBuffer:
            if (rreq.requestID,rreq.originatorAdress) == entry:
                return
        rreq.incrementHopCount()
        self.reverseRoutingTable.updateEntryWithRREQ(rreq)
        if rreq.destinationAdress is not self.ownAdress:
            if self.routingTable.hasEntryForDestination(rreq.destinationAdress):
                self.send("FFFF", rreq.encode())
                return
        self.generateRREP(rreq)
        
    
    def processRREP(self, rrep: RouteReply):
        self.routingTable.updateEntryWithDestination(rrep.previousHop)
        rrep.incrementHopCount()
        self.routingTable.updateEntryWithRREP(rrep)
        try:
            reverseRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
            reverseRoute.lifetime = max(reverseRoute.lifetime,int(time()*1000)+AODV.ACTIVE_ROUTE_TIMEOUT)
            forwardRoute = self.routingTable.getEntry(rrep.destinationAdress)
            forwardRoute.precursers.append(reverseRoute.nextHop)
            nextHopRoute = self.routingTable.getEntry(reverseRoute.nextHop)
            nextHopRoute.precursers.append(rrep.originatorAdress)
            if rrep.originatorAdress != self.ownAdress:
                self.send(reverseRoute.nextHop,rrep.encode())
        except Exception as err:
            self.logger.error(err)

    def send(self, destinationAdress: str, payload: str):
        self.logger.debug("Sending: "+payload+" to: "+destinationAdress)
        msgLenght = len(payload)
        adressCMD = "AT+DEST="+destinationAdress
        sendCMD = "AT+SEND="+str(msgLenght)
        self.outputQueue.put(adressCMD)
        self.outputQueue.put(sendCMD)
        self.outputQueue.put(payload)

    def sendUserData(self, destination: str, data: str):
        userData = UserData()
        userData.destinationAdress = destination
        userData.userData = data.encode("utf-8")
        if self.routingTable.hasEntryForDestination(destination):
            self.send(self.routingTable.getEntry(destination).nextHop,userData.encode())
            return
        self.generateRREQ(userData.destinationAdress,True,0)
        self.userDataBuffer.append(userData)
            

    def generateRREP(self, rreq: RouteRequest):
        rrep = RouteReply()
        if rreq.destinationAdress == self.ownAdress:
            rrep.destinationAdress = self.ownAdress
            rrep.originatorAdress = self.ownAdress
            rrep.destinationSequence = self.sequenceNumber
            rrep.hopCount = int(0)
            rrep.lifetime = AODV.MY_ROUTE_TIMEOUT
            self.incrementSequenceNumber()
            if not self.sequenceNumber == rreq.destinationSequence:
                self.decrementSequenceNumber()
            rrep.destinationSequence = self.sequenceNumber
            self.send(rreq.originatorAdress, rrep.encode())
            return
        if self.routingTable.hasEntryForDestination(rreq.destinationAdress):
            forwardRoute = self.routingTable.getEntry(rreq.destinationAdress)
            reverseRoute = self.reverseRoutingTable.getEntry(rreq.originatorAdress)
            rrep.destinationSequence = forwardRoute.destinationSequenceNumber
            forwardRoute.precursers.append(rreq.previousHop)
            reverseRoute.precursers.append(forwardRoute.nextHop)
            rrep.hopCount = forwardRoute.hopCount
            rrep.destinationAdress = rreq.destinationAdress
            rrep.originatorAdress = self.ownAdress
            rrep.destinationSequence = self.sequenceNumber
            rrep.lifetime = forwardRoute.lifetime - int(time()*1000)
            self.send(rreq.originatorAdress, rrep.encode())

    def checkForResponse(self, userData: UserData):
        waitingTime = self.NET_TRAVERSAL_TIME
        while userData.numRetries <= self.RREQ_RETRIES:
            if self.routingTable.hasEntryForDestination(userData.destinationAdress):
                return
            sleep(waitingTime)
            userData.numRetries +=1
            self.generateRREQ(userData.destinationAdress,True,0)
            waitingTime = 2^userData.numRetries*self.NET_TRAVERSAL_TIME

    def generateRREQ(self, destinationAdress: str,isSequenceNumberUnknown: bool, destinationSequenceNumber: str):
        rreq = RouteRequest()
        if isSequenceNumberUnknown:
            rreq.unknownSequenceNumber = True
        self.incrementSequenceNumber()
        rreq.originatorSequence = self.sequenceNumber
        self.incrementRequestID()
        rreq.requestID = self.requestID
        rreq.hopCount = 0
        rreq.destinationAdress = destinationAdress
        rreq.originatorAdress = self.ownAdress
        self.rreqBuffer.append((rreq.requestID,rreq.originatorAdress))
        self.send("FFFF", rreq.encode())

    def parse(self, msg:str):
        msgList = msg.split(",")
        addrStr = msgList[1]
        payload = msgList[3]
        self.logger.debug("Parsed: "+payload+" from: "+addrStr)
        payloadMatch = re.match("^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",payload)# check for BASE64 String
        if payloadMatch is None:
            self.logger.error("Payload not BASE64 encoded: "+payload)
            return
        type = self.getPackageType(payload)
        if type == 1:
            package = RouteRequest()
            self.logger.debug("Recieved RREQ from "+addrStr)
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREQ(package)
        if type == 2:
            package = RouteReply()
            self.logger.debug("Recieved RREP from "+addrStr)
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREP(package)
        

    def getPackageType(self, msg: str):
        base64_bytes = msg
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        type = byteArray[:6].uint
        return type