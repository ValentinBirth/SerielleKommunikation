import base64
import bitstring
import re
from queue import Queue
from SerComClient import SerCom

class Route:
    def __init__(self, destinationAdress: str, destinationSequenceNumber: int, isDestinationSequenceNumberValid: bool, hopCount: int, nextHop: str, precursers: list, lifetime: int):
        self.destinationAdress = destinationAdress
        self.destinationSeqNum = destinationSequenceNumber
        self.isDestinationSequenceNumberValid = isDestinationSequenceNumberValid
        self.hopCount = hopCount
        self.nextHop = nextHop
        self.precursers = precursers
        self.lifetime = lifetime

class RoutingTable:
    table = {}

    def hasEntryForDestination(self, destination: str) -> bool:
        return self.table.get(destination) != None

    def getEntry(self, destination: str) -> Route:
        return self.table.get(destination)

    def addEntry(self, route: Route):
        self.table[route.destinationAdress] = route

    def updateEntry(self, new: Route):
        self.table.update({new.destinationAdress : new})

class RouteRequest:
    type = 1      
    flagOne = False
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
    format = "uint6=type, bool1=flagOne, bool1=flagTwo, bool1=flagThree, bool1=flagFour, bool1=flagFive, bool1=flagSix, uint6=hopCount, uint6=requestID, hex16=destinationAdress, int8=destinationSequence, hex16=originatorAdress, uint8=originatorSequence"

    def decode(self, msg: str):
        base64_bytes = msg.encode("ascii")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        arglist = byteArray.unpack(self.format)
        self.type = arglist[0]
        self.flagOne = arglist[1]
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

class AODV:
    routingTable = RoutingTable()
    reverseRoutingTable = RoutingTable()
    lastAdress = None
    ownAdress = None
    sequenceNumber = 0
    inputQueue = Queue(maxsize=0)
    outputQueue = Queue(maxsize=0)
    rreqBuffer = Queue(maxsize=0)
    serialPortClient = SerCom(inputQueue,outputQueue)

    ACTIVE_ROUTE_TIMEOUT = 3
    TIMEOUT_BUFFER = 2 
    TTL_START = 1 
    TTL_INCREMENT = 2 
    TTL_THRESHOLD = 7 
    TTL_VALUE = None # Lifetime Value of Package
    ALLOWED_HELLO_LOSS = 2 
    RREQ_RETRIES = 2 
    NODE_TRAVERSAL_TIME = 40 
    NET_DIAMETER = 35
    NET_TRAVERSAL_TIME = 2 * NODE_TRAVERSAL_TIME * NET_DIAMETER 
    BLACKLIST_TIMEOUT = RREQ_RETRIES * NET_TRAVERSAL_TIME 
    DELETE_PERIOD = None #see note in RFC
    HELLO_INTERVAL = 1
    LOCAL_ADD_TTL = 2 
    MAX_REPAIR_TTL = 0.3 * NET_DIAMETER
    MIN_REPAIR_TTL= None # last known hop count
    MY_ROUTE_TIMEOUT = 2 * ACTIVE_ROUTE_TIMEOUT 
    NEXT_HOP_WAIT = NODE_TRAVERSAL_TIME + 10 
    PATH_DISCOVERY_TIME = 2 * NET_TRAVERSAL_TIME 
    RERR_RATELIMIT = 10 
    RING_TRAVERSAL_TIME = 2 * NODE_TRAVERSAL_TIME * (TTL_VALUE + TIMEOUT_BUFFER) 
    RREQ_RATELIMIT = 10 

    def isMSGStale(currentEntry, newEntry):
        if newEntry.flagOne:
            return False
        if currentEntry.destinationSeqNum == newEntry.destinationSeqNum and newEntry.hopCount+1 < currentEntry.hopCount:
            return False
        if newEntry.destinationSeqNum-currentEntry.destinationSeqNum < 0:
            return True

    def send(destinationAdress: str, msg: str):
        ...

    def updateRoute(self, package):
        #TODO create Update Route Method
        ...

    def generateRREP(self, RREQ: RouteRequest) -> bool:
        if RREQ.destinationAdress == self.ownAdress:
            if self.sequenceNumber+1 == RREQ.destinationSequence:
                self.sequenceNumber = self.sequenceNumber+1
            RREP = RouteReply()
            RREP.destinationAdress = RREQ.destinationAdress
            RREP.destinationSequence = self.sequenceNumber
            RREP.lifetime = self.MY_ROUTE_TIMEOUT
            self.serialPortClient.send(RREP.encode())
            return True
        if self.routingTable.hasEntryForDestination(RREQ.destinationAdress):
            RREP = RouteReply()
            entry = self.routingTable.getEntry(RREQ.destinationAdress)
            entry.precursers.append(self.lastAdress)
            reverseEntry = self.reverseRoutingTable.getEntry(RREQ.originatorAdress)
            reverseEntry.precursers.append(entry.nextHop)
            self.routingTable.updateEntry(entry)
            self.reverseRoutingTable.updateEntry(reverseEntry)
            RREP.destinationSequence = entry.destinationSeqNum
            RREP.hopCount = entry.hopCount
            RREP.lifetime = entry.lifetime #laut RFC auch minus current time ??
            return True
        return False

    def processRREQ(self, RREQ: RouteRequest):
        self.updateRoute(RREQ)
        for package in self.rreqBuffer:
            if RREQ.originatorAdress == package.originatorAdress and RREQ.requestID == package.requestID:
                return
        RREQ.hopCount = RREQ.hopCount+1
        if self.reverseRoutingTable.hasEntryForDestination(RREQ.originatorAdress):
            oldEntry = self.reverseRoutingTable.getEntry(RREQ.destinationAdress)
            sequenceNumber = oldEntry.destinationSeqNum
            if RREQ.originatorSequence > oldEntry.destinationSeqNum:
                sequenceNumber = RREQ.originatorSequence
            newEntry = Route(RREQ.destinationAdress,sequenceNumber, True, RREQ.hopCount, self.lastAdress, None, None)
            self.reverseRoutingTable.updateEntry(newEntry)
        else:
            newEntry = Route(RREQ.destinationAdress,RREQ.originatorSequence, True, RREQ.hopCount, self.lastAdress, None, None)
            self.reverseRoutingTable.addEntry(newEntry)
        if not self.generateRREP(RREQ):
            RREQ.hopCount = RREQ.hopCount+1
            self.serialPortClient.send(RREQ.encode())
        #6.5 Unterschied zwischen Update und create
        #6.5 lifetime der Reverse Route
        #6.5 Sequenz Nummer beim Updaten und weiterleiten des RREQ ?
        


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