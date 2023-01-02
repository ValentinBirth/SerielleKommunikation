import base64
import bitstring
import re
from time import time
from queue import Queue
import logging

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

class RouteRequest:
    logger = logging.getLogger(__name__)
    type = 1      
    unknownSequenceNumber = False
    flagTwo = False
    flagThree = False
    flagFour = False
    flagFive = False
    flagSix = False
    hopCount = 0
    requestID = 0
    destinationAdress = "000F"
    destinationSequence = 0
    originatorAdress = "000F"
    originatorSequence = 0
    format = "uint6=type, bool1=unknownSequenceNumber, bool1=flagTwo, bool1=flagThree, bool1=flagFour, bool1=flagFive, bool1=flagSix, uint6=hopCount, uint6=requestID, hex16=destinationAdress, int8=destinationSequence, hex16=originatorAdress, uint8=originatorSequence"

    previousHop = ""

    def decode(self, msg: str):
        base64_bytes = msg.encode("ascii")
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
        return base64string.decode("ascii")

class RouteReply:
    type = 2
    lifetime = None
    destinationAdress = None
    destinationSequence = None
    originatorAdress = None
    hopCount = 0
    format = "uint6=type, uint18=lifetime, hex16=destinationAdress, int8=destinationSequence, hex16=originatorAdress, uint8=hopCount"
    
    previousHop = ""

    def decode(self, msg: str):
        base64_bytes = msg.encode("ascii")
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
        byteArray = bitstring.pack(self.format, **self.__dict__)
        base64string = base64.b64encode(byteArray.tobytes())
        return base64string.decode("ascii")

class RoutingTable:
    table = {}
    logger = logging.getLogger(__name__)

    def isUpdatedNeeded(self,currentEntry: Route, newEntry: Route) -> bool:
        if not newEntry.isDestinationSequenceNumberValid:
            return True
        if newEntry.destinationSequenceNumber-currentEntry.destinationSequenceNumber < 0:
            return True
        if currentEntry.destinationSequenceNumber == newEntry.destinationSequenceNumber and newEntry.hopCount < currentEntry.hopCount:
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
    routingTable = RoutingTable()
    reverseRoutingTable = RoutingTable()
    ownAdress = None
    sequenceNumber = 0
    requestID = 0
    rreqBuffer = []
    logger = logging.getLogger(__name__)

    ACTIVE_ROUTE_TIMEOUT = 3000
    NODE_TRAVERSAL_TIME = 40
    MY_ROUTE_TIMEOUT = 2 * ACTIVE_ROUTE_TIMEOUT
    NET_TRAVERSAL_TIME =2 * NODE_TRAVERSAL_TIME # * NET_DIAMETER
    PATH_DISCOVERY_TIME = 2 * NET_TRAVERSAL_TIME
    RREQ_RETRIES = 2

    def processRREQ(self, rreq: RouteRequest):
        self.logger.debug(rreq.__dict__)
        self.routingTable.updateEntryWithDestination(rreq.previousHop)
        for entry in self.rreqBuffer:
            if (rreq.requestID,rreq.originatorAdress) == entry:
                return
        rreq.hopCount += 1
        self.reverseRoutingTable.updateEntryWithRREQ(rreq)
        if rreq.destinationAdress is not self.ownAdress or not self.routingTable.hasEntryForDestination(rreq.destinationAdress):
            self.send("FFFF", rreq.encode())
            return
        self.generateRREP(rreq)
        
    
    def processRREP(self, rrep: RouteReply):
        self.routingTable.updateEntryWithDestination(rrep.previousHop)
        rrep.hopCount += 1
        self.routingTable.updateEntryWithRREP(rrep)
        reverseRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
        reverseRoute.lifetime = max(reverseRoute.lifetime,int(time()*1000)+AODV.ACTIVE_ROUTE_TIMEOUT)
        forwardRoute = self.routingTable.getEntry(rrep.destinationAdress)
        forwardRoute.precursers.append(reverseRoute.nextHop)
        nextHopRoute = self.routingTable.getEntry(reverseRoute.nextHop)
        nextHopRoute.precursers.append(rrep.originatorAdress)
        self.send(reverseRoute.nextHop,rrep.encode())

    def send(self, destinationAdress: str, payload: str):
        self.logger.debug("Sending: "+payload+" to: "+destinationAdress)
        msgLenght = len(payload)
        adressCMD = "AT+DEST="+destinationAdress
        sendCMD = "AT+SEND="+str(msgLenght)
        self.outputQueue.put(adressCMD)
        self.outputQueue.put(sendCMD)
        self.outputQueue.put(payload)

    def generateRREP(self, rreq: RouteRequest):
        rrep = RouteReply()
        if rreq.destinationAdress == self.ownAdress:
            rrep.hopCount = 0
            rrep.lifetime = AODV.MY_ROUTE_TIMEOUT
            if self.sequenceNumber+1 == rreq.destinationSequence:
                self.sequenceNumber += 1
            rrep.destinationSequence = self.sequenceNumber
            return
        if self.routingTable.hasEntryForDestination(rreq.destinationAdress):
            forwardRoute = self.routingTable.getEntry(rreq.destinationAdress)
            reverseRoute = self.reverseRoutingTable.getEntry(rreq.originatorAdress)
            rrep.destinationSequence = forwardRoute.destinationSequenceNumber
            forwardRoute.precursers.append(rreq.previousHop)
            reverseRoute.precursers.append(forwardRoute.nextHop)
            rrep.hopCount = forwardRoute.hopCount
            rrep.lifetime = forwardRoute.lifetime - int(time()*1000)
        self.send(rreq.originatorAdress, rrep.encode())

    def waitForResponse(self):
        ...

    def generateRREQ(self, isSequenceNumberUnknown: bool, destinationSequenceNumber: str):
        rreq = RouteRequest()
        if isSequenceNumberUnknown:
            rreq.unknownSequenceNumber = True
        self.sequenceNumber += 1
        rreq.originatorSequence = self.sequenceNumber
        self.requestID += 1
        rreq.requestID = self.requestID
        rreq.hopCount = 0
        self.rreqBuffer.append((rreq.requestID,rreq.originatorAdress))
        self.send("FFFF", rreq.encode())
        self.waitForResponse()

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