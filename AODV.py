import base64
import bitstring
from time import time, sleep
from queue import Queue
import logging
import threading

# TODO
# implement startup/reboot sequence
# reverse Route not established correctly
# Userdata encoding not working
# improve taular output

class Route:
    def __init__(self) -> None:
        self.destinationAdress = ""
        self.destinationSequenceNumber = 0
        self.isDestinationSequenceNumberValid = False
        self.hopCount = 0
        self.nextHop = ""
        self.precursers = []
        self.lifetime = 0
        self.active = False

    def __str__(self) -> str:
        return str(self.__dict__)

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
        udbin = bitstring.BitArray(bytes=str(self.userData).encode("utf-8"))
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

    def __str__(self) -> str:
        return f"Unknown Sequence Number: {self.unknownSequenceNumber}\nHopcount: {self.hopCount}\nRequest ID: {self.requestID}\nDestination Adress: {self.destinationAdress}\nDestination Sequence Number: {self.destinationSequence}\nOriginator Adress: {self.originatorAdress}\nOriginator Sequence Number: {self.originatorSequence}\n"

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

    def __str__(self) -> str:
        return f"Lifetime: {self.lifetime}\nHopcount: {self.hopCount}\nDestination Adress: {self.destinationAdress}\nDestination Sequence Number: {self.destinationSequence}\nOriginator Adress: {self.originatorAdress}\n"
class RoutingTable:
    def getTable(self) -> list:
        routeDict = {}
        for route in self.table:
            routeDict[route] = str(self.table.get(route))
        return list(routeDict.items())

    def checkForRouteLifetime(self):
        while True:
            with self.tableLock:
                if len(self.table) > 0:
                    for destination in list(self.table):
                        route = self.table[destination]
                        routeLifetime = route.lifetime
                        timestampMS = int(time()*1000)
                        if routeLifetime - timestampMS < 0:
                            self.table.pop(destination)
            sleep(0.01)

    def __init__(self) -> None:
        self.table = {}
        self.tableLock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.readThread = threading.Thread(target=self.checkForRouteLifetime, daemon=True).start()

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
        if not newEntry.active:
            return True
        if differenceWithOverflow < 0:
            return True
        if currentDestSeqNum == newDestSeqNum and newEntry.hopCount < currentEntry.hopCount:
            return True

    def getEntry(self, destination: str) -> Route:
        with self.tableLock:
            return self.table.get(destination)

    def updateEntry(self, newEntry: Route) -> None:
        with self.tableLock:
            self.table.update({newEntry.destinationAdress : newEntry})

    def hasEntryForDestination(self, destination: str) -> bool:
        entry = self.getEntry(destination)
        if entry is not None:
            self.logger.debug(entry.__dict__)
            return True
        self.logger.debug("No Entry for "+destination+" found")

    def hasValidEntryForDestination(self, destination: str) -> bool:
        entry = self.getEntry(destination)
        if entry is not None and entry.active:
            self.logger.debug(entry.__dict__)
            return True
        self.logger.debug("No Entry for "+destination+" found")

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
            newRoute.active = False
            self.updateEntry(newRoute)

    def updateEntryWithRREP(self, rrep: RouteReply):
        self.logger.debug("Updating Route to "+rrep.destinationAdress)
        newRoute = Route()
        newRoute.isDestinationSequenceNumberValid = True
        newRoute.destinationSequenceNumber = rrep.destinationSequence
        newRoute.destinationAdress = rrep.destinationAdress
        newRoute.lifetime = int(time()*1000)+rrep.lifetime
        newRoute.nextHop = rrep.previousHop
        newRoute.active = True
        newRoute.hopCount = rrep.hopCount
        oldRoute = self.getEntry(rrep.destinationAdress)
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.updateEntry(newRoute)

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
            self.updateEntry(newRoute)


logging.basicConfig(level=logging.DEBUG)
class AODV:
    ACTIVE_ROUTE_TIMEOUT = int(3000)
    NODE_TRAVERSAL_TIME = int(40)
    MY_ROUTE_TIMEOUT = 2 * ACTIVE_ROUTE_TIMEOUT
    NET_TRAVERSAL_TIME =2 * NODE_TRAVERSAL_TIME # * NET_DIAMETER
    PATH_DISCOVERY_TIME = 2 * NET_TRAVERSAL_TIME
    RREQ_RETRIES = int(2)
    def __init__(self, outputQueue: Queue):
        self.outputQueue = outputQueue
        self.routingTable = RoutingTable()
        self.reverseRoutingTable = RoutingTable()
        self.ownAdress = None
        self.sequenceNumber = 0
        self.requestID = 0
        self.rreqBuffer = {}
        self.userDataBuffer = []
        self.userDataBufferLock = threading.Lock()
        self.rreqBufferLock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.readThread = threading.Thread(target=self.checkForResponse, daemon=True).start()
        self.readThread = threading.Thread(target=self.checkRREQBuffer, daemon=True).start()

    def incrementSequenceNumber(self):
        self.sequenceNumber += 1
        self.sequenceNumber = self.sequenceNumber % 255

    def decrementSequenceNumber(self):
        self.sequenceNumber -= 1
        self.sequenceNumber = self.sequenceNumber % 255

    def incrementRequestID(self):
        self.requestID += 1
        self.requestID = self.requestID % 63

    def getUserDataBuffer(self) -> list:
        udStrList = []
        for ud in self.userDataBuffer:
            udStrList.append(str(ud.__dict__))
        return udStrList

    def processRREQ(self, rreq: RouteRequest):
        self.logger.debug(rreq.previousHop+" send RREQ with:\n"+str(rreq))
        #self.routingTable.updateEntryWithDestination(rreq.previousHop)
        with self.rreqBufferLock:
            for entry in self.rreqBuffer:
                if (rreq.requestID,rreq.originatorAdress) == entry:
                    return
        rreq.incrementHopCount()
        self.reverseRoutingTable.updateEntryWithRREQ(rreq)
        if rreq.destinationAdress is not self.ownAdress:
            if self.routingTable.hasValidEntryForDestination(rreq.destinationAdress):
                self.send("FFFF", rreq.encode())
                return
        self.generateRREP(rreq)
        
    
    def processRREP(self, rrep: RouteReply):
        self.logger.debug(rrep.previousHop+" send RREP with:\n"+str(rrep))
        #self.routingTable.updateEntryWithDestination(rrep.previousHop)
        rrep.incrementHopCount()
        self.routingTable.updateEntryWithRREP(rrep)
        reverseRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
        if reverseRoute is not None:
            self.logger.debug("Process RREP RRTE: "+str(reverseRoute))
            reverseRoute.lifetime = max(reverseRoute.lifetime,int(time()*1000)+AODV.ACTIVE_ROUTE_TIMEOUT)
            forwardRoute = self.routingTable.getEntry(rrep.destinationAdress)
            forwardRoute.precursers.append(reverseRoute.nextHop)
            nextHopRoute = self.routingTable.getEntry(reverseRoute.nextHop)
            nextHopRoute.precursers.append(rrep.originatorAdress)
            if rrep.originatorAdress != self.ownAdress:
                self.send(reverseRoute.nextHop,rrep.encode())
            return
        self.logger.error("No Reverse Route found for RREP")

    def processUD(self, ud:UserData):
        if ud.destinationAdress != self.ownAdress:
            forwardRoute = self.routingTable.getEntry(ud.destinationAdress)
            self.send(forwardRoute.nextHop,ud.encode())
            return
        self.logger.debug(ud.__dict__)
        print(ud.userData)

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
        if self.routingTable.hasValidEntryForDestination(destination):
            self.send(self.routingTable.getEntry(destination).nextHop,userData.encode())
            return
        self.generateRREQ(userData.destinationAdress,True,0)
        with self.userDataBufferLock:
            self.userDataBuffer.append(userData)
            

    def generateRREP(self, rreq: RouteRequest):
        self.logger.debug("Generate RREP for "+rreq.destinationAdress)
        rrep = RouteReply()
        if rreq.destinationAdress == self.ownAdress:
            rrep.destinationAdress = self.ownAdress
            rrep.originatorAdress = rreq.originatorAdress
            rrep.destinationSequence = self.sequenceNumber
            rrep.hopCount = int(0)
            rrep.lifetime = AODV.MY_ROUTE_TIMEOUT
            self.incrementSequenceNumber()
            if not self.sequenceNumber == rreq.destinationSequence:
                self.decrementSequenceNumber()
            rrep.destinationSequence = self.sequenceNumber
            self.send(rreq.originatorAdress, rrep.encode())
            return
        if self.routingTable.hasValidEntryForDestination(rreq.destinationAdress):
            forwardRoute = self.routingTable.getEntry(rreq.destinationAdress)
            reverseRoute = self.reverseRoutingTable.getEntry(rreq.originatorAdress)
            rrep.destinationSequence = forwardRoute.destinationSequenceNumber
            forwardRoute.precursers.append(rreq.previousHop)
            reverseRoute.precursers.append(forwardRoute.nextHop)
            rrep.hopCount = forwardRoute.hopCount
            rrep.destinationAdress = rreq.destinationAdress
            rrep.originatorAdress = rreq.originatorAdress
            rrep.destinationSequence = self.sequenceNumber
            rrep.lifetime = forwardRoute.lifetime - int(time()*1000)
            self.send(rreq.originatorAdress, rrep.encode())
            return
        self.logger.error("No route to "+rreq.destinationAdress +" exist")

    def checkForResponse(self):
        while True:
            with self.userDataBufferLock:
                if len(self.userDataBuffer) > 0:
                    for userData in self.userDataBuffer:
                        waitingTime = AODV.NET_TRAVERSAL_TIME
                        if userData.numRetries > AODV.RREQ_RETRIES:
                            self.userDataBuffer.remove(userData)
                            self.logger.error("Destimation "+userData.destinationAdress +" unreachable")
                        while userData.numRetries <= AODV.RREQ_RETRIES:
                            if self.routingTable.hasValidEntryForDestination(userData.destinationAdress):
                                self.send(self.routingTable.getEntry(userData.destinationAdress).nextHop,userData.encode())
                                continue
                            sleep(waitingTime)
                            userData.numRetries +=1
                            self.generateRREQ(userData.destinationAdress,True,0)
                            waitingTime = 2^userData.numRetries*AODV.NET_TRAVERSAL_TIME
            sleep(AODV.NET_TRAVERSAL_TIME)

    def generateRREQ(self, destinationAdress: str,isSequenceNumberUnknown: bool, destinationSequenceNumber: str):
        self.logger.debug("Generating RREQ to "+destinationAdress)
        rreq = RouteRequest()
        if isSequenceNumberUnknown:
            rreq.unknownSequenceNumber = True
        rreq.destinationSequence = destinationSequenceNumber
        self.incrementSequenceNumber()
        rreq.originatorSequence = self.sequenceNumber
        self.incrementRequestID()
        rreq.requestID = self.requestID
        rreq.hopCount = 0
        rreq.destinationAdress = destinationAdress
        rreq.originatorAdress = self.ownAdress
        with self.rreqBufferLock:
            self.rreqBuffer[(rreq.requestID,rreq.originatorAdress)] = int(time()*1000)
        self.send("FFFF", rreq.encode())

    def parse(self, msg:str):
        msgList = msg.split(",")
        addrStr = msgList[1]
        payload = msgList[3]
        #payloadMatch = re.match("^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",payload)# check for BASE64 String
        #if payloadMatch is None:
        #    self.logger.error("Payload not BASE64 encoded: "+payload)
        #    return
        type = self.getPackageType(payload)
        if type == 0:
            package = UserData()
            package.decode(payload)
            package.previousHop = addrStr
            self.processUD(package)
        if type == 1:
            package = RouteRequest()
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREQ(package)
        if type == 2:
            package = RouteReply()
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREP(package)
        

    def getPackageType(self, msg: str):
        base64_bytes = msg
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        type = byteArray[:6].uint
        return type

    def checkRREQBuffer(self):
        while True:
            with self.rreqBufferLock:
                if len(self.rreqBuffer) > 0:
                    for entry in list(self.rreqBuffer):
                        entryTimeStamp = self.rreqBuffer[entry]
                        entryTimeStamp += AODV.PATH_DISCOVERY_TIME
                        timestampMS = int(time()*1000)
                        if entryTimeStamp - timestampMS < 0:
                            self.rreqBuffer.pop(entry)
            sleep(AODV.PATH_DISCOVERY_TIME)