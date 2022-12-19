import base64
import bitstring
import re
from time import time
from queue import Queue
from SerComClient import SerCom

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

    format = "uint6=type, unit18=lifetime, hex16=destinationAdress, int8=destinationSequence, hex16=originatorAdress, uint8=hopCount"
    
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

    def isUpdatedNeeded(self,currentEntry, newEntry) -> bool:
        if not newEntry.isDestinationSequenceNumberValid:
            return True
        if newEntry.destinationSeqNum-currentEntry.destinationSeqNum < 0:
            return True
        if currentEntry.destinationSeqNum == newEntry.destinationSeqNum and newEntry.hopCount < currentEntry.hopCount:
            return True

    def hasEntryForDestination(self, destination: str) -> bool:
        return self.table.get(destination) != None

    def getEntry(self, destination: str) -> Route:
        return self.table.get(destination)

    def updateEntryWithDestination(self,destinationAdress: str):
        if not self.hasEntryForDestination(destinationAdress):
            newRoute = Route()
            newRoute.isDestinationSequenceNumberValid = False
            newRoute.destinationSequenceNumber = 0
            newRoute.destinationAdress = destinationAdress
            newRoute.lifetime = int(time()*1000)+AODV.ACTIVE_ROUTE_TIMEOUT 
            newRoute.hopCount = 1
            newRoute.nextHop = destinationAdress
            newRoute.active = True
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntryWithRREP(self, rrep: RouteReply, previousHopAdress: str):
        newRoute = Route()
        newRoute.isDestinationSequenceNumberValid = True
        newRoute.destinationSequenceNumber = rrep.destinationSequence
        newRoute.destinationAdress = rrep.destinationAdress
        newRoute.lifetime = int(time()*1000)+rrep.lifetime
        newRoute.nextHop = previousHopAdress
        newRoute.active = True
        oldRoute = self.getEntry(rrep.destinationAdress)
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntryWithRREQ(self, rreq: RouteRequest, previousHopAdress: str):
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
        newRoute.nextHop = previousHopAdress
        newRoute.hopCount = rreq.hopCount
        newRoute.active = True
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.table.update({newRoute.destinationAdress : newRoute})

    def updateEntry(self, route: Route):
        self.table.update({route.destinationAdress : route})

class AODV:
    routingTable = RoutingTable()
    reverseRoutingTable = RoutingTable()
    lastAdress = None
    ownAdress = None
    sequenceNumber = 0
    lastRequestID = 0
    inputQueue = Queue(maxsize=0)
    outputQueue = Queue(maxsize=0)
    rreqBuffer = []
    serialPortClient = SerCom(inputQueue,outputQueue)

    ACTIVE_ROUTE_TIMEOUT = 3000
    NODE_TRAVERSAL_TIME = 40
    MY_ROUTE_TIMEOUT = 2 * ACTIVE_ROUTE_TIMEOUT
    NET_TRAVERSAL_TIME =2 * NODE_TRAVERSAL_TIME # * NET_DIAMETER
    PATH_DISCOVERY_TIME = 2 * NET_TRAVERSAL_TIME
    RREQ_RETRIES = 2

    def processRREQ(self, rreq: RouteRequest):
        self.routingTable.updateEntryWithDestination(self.lastAdress)
        for entry in self.rreqBuffer:
            if (rreq.requestID,rreq.originatorAdress) == entry:
                return
        rreq.hopCount += 1
        self.reverseRoutingTable.updateEntryWithRREQ(rreq,self.lastAdress)
        if rreq.destinationAdress is not self.ownAdress or not self.routingTable.hasEntryForDestination(rreq.destinationAdress):
            self.send("FFFF", rreq.encode())
            return
        self.generateRREP(rreq,self.lastAdress)
        
    
    def processRREP(self, rrep: RouteReply):
        self.routingTable.updateEntryWithDestination(self.lastAdress)
        rrep.hopCount += 1
        self.routingTable.updateEntryWithRREP(rrep,self.lastAdress)
        destRoute = self.routingTable.getEntry(rrep.destinationAdress)
        destRoute.precursers.append(destRoute.nextHop)
        destRoute.lifetime = max(destRoute.lifetime, int(time*1000)+AODV.ACTIVE_ROUTE_TIMEOUT)
        sourceRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
        sourceRoute.precursers.append(sourceRoute.nextHop)
        self.send(destRoute.nextHop,rrep.encode())

    def send(destinationAdress: str, msg: str):
        ...

    def generateRREP(self, rreq: RouteRequest, previousAdress: str):
        rrep = RouteReply()
        if rreq.destinationAdress == self.ownAdress:
            rrep.lifetime = AODV.MY_ROUTE_TIMEOUT
            if self.sequenceNumber+1 == rreq.destinationSequence:
                self.sequenceNumber += 1
            rrep.destinationSequence = self.sequenceNumber
            return
        route = self.routingTable.getEntry(rreq.destinationAdress)
        route.precursers.append(previousAdress)
        reverseRoute = self.reverseRoutingTable.getEntry(rreq.originatorAdress)
        reverseRoute.precursers = route.nextHop
        self.routingTable.updateEntry(route)
        self.reverseRoutingTable.updateEntry(reverseRoute)
        rrep.destinationSequence = route.destinationSequenceNumber
        rrep.hopCount = route.hopCount
        rrep.lifetime = route.lifetime - int(time()*1000)
        self.send(rreq.originatorAdress, rrep.encode())

    def waitForResponse(self):
        ...

    def generateRREQ(self, isSequenceNumberUnknown: bool, destinationSequenceNumber: str):
        rreq = RouteRequest()
        if isSequenceNumberUnknown:
            rreq.unknownSequenceNumber = True
        rreq.destinationSequence = destinationSequenceNumber
        self.sequenceNumber += 1
        rreq.originatorSequence = self.sequenceNumber
        rreq.requestID = self.lastRequestID+1
        self.rreqBuffer.append((rreq.requestID,rreq.originatorAdress))
        self.send("FFFF", rreq.encode())
        self.waitForResponse()

    def parse(self, msg:str):
        msgMatch = re.match("LR, ?[0-9A-F]{4}, ?[0-9A-F]{2}, ?", msg)
        if msgMatch != None:
            msg = msgMatch.group()
            addrStr = msg.split(",")[1].strip()
            self.lastAdress = addrStr
        payload = msg.strip(",")[3]
        package = self.decode(payload)

    def decode(self, msg: str):
        base64_bytes = msg.encode("ascii")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        type = byteArray[0:6].uint
        if type == 1:
            package = RouteRequest()
            print("Got RREQ")
        package.decode(msg)
        return package