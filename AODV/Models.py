from . import Constants
import logging
import base64
import bitstring
from time import time, sleep
import threading

## TODO
logging.basicConfig(level=logging.DEBUG)
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

    def asList(self):
        return [self.destinationAdress,self.destinationSequenceNumber,self.isDestinationSequenceNumberValid,self.hopCount,self.nextHop,self.precursers,self.lifetime,self.active]

    def __str__(self) -> str:
        return str(self.asList())

class UserData:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.type = 0
        self.destinationAdress = ""
        self.userData = ""
        self.userDataBin = ""
        self.numRetries = 0

        self.format = "uint6=type, hex16=destinationAdress"
        self.unpackformat = self.format + ", bits=userDataBin"
        self.previousHop = None

    def decode(self, msg: str):
        base64_bytes = msg.encode("utf-8")
        message_bytes = base64.b64decode(base64_bytes)
        byteArray = bitstring.BitArray(bytes=message_bytes)
        arglist = byteArray.unpack(self.unpackformat)
        self.type = arglist[0]
        self.destinationAdress = arglist[1]
        self.userData = arglist[2].tobytes().decode("utf-8")
    
    def encode(self):
        byteArray = bitstring.pack(self.format, **self.__dict__)
        udbin = bitstring.BitArray(bytes=str(self.userData).encode("utf-8"))
        byteArray.append(udbin)
        base64string = base64.b64encode(byteArray.tobytes())
        return base64string.decode("utf-8")

    def __str__(self) -> str:
        return f"""------User Data from {self.previousHop}---------
Destination Adress: {self.destinationAdress}
User Data: {self.userData}
-----------------------------------"""

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
        self.previousHop = None

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
        return f"""---------RREQ from {self.previousHop}------------
Unknown Sequence Number: {self.unknownSequenceNumber}
Hopcount: {self.hopCount}
Request ID: {self.requestID}
Destination Adress: {self.destinationAdress}
Destination Sequence Number: {self.destinationSequence}
Originator Adress: {self.originatorAdress}
Originator Sequence Number: {self.originatorSequence}
-----------------------------------"""

class RouteReply:
    def __init__(self) -> None:
        self.type = 2
        self.lifetime = None
        self.destinationAdress = None
        self.destinationSequence = None
        self.originatorAdress = None
        self.hopCount = 0
        self.format = "uint6=type, uint18=lifetime, hex16=destinationAdress, uint8=destinationSequence, hex16=originatorAdress, uint8=hopCount"
        
        self.previousHop = None

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
        return f"""---------RREP from {self.previousHop}------------
Lifetime: {self.lifetime}
Hopcount: {self.hopCount}
Destination Adress: {self.destinationAdress}
Destination Sequence Number: {self.destinationSequence}
Originator Adress: {self.originatorAdress}
-----------------------------------"""

class RoutingTable:
    def getTable(self) -> list:
        rtList = []
        for route in self.table:
            rtList.append(self.getEntry(route).asList())
        return rtList

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
            sleep(Constants.MY_ROUTE_TIMEOUT/1000)

    def __init__(self) -> None:
        self.table = {}
        self.tableLock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.routeLifetimeCheckThread = threading.Thread(target=self.checkForRouteLifetime, daemon=True)
        self.routeLifetimeCheckThread.start()

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
            self.table.update(({newEntry.destinationAdress : newEntry}))

    def hasEntryForDestination(self, destination: str) -> bool:
        entry = self.getEntry(destination)
        if entry is not None:
            #self.logger.debug(entry.__dict__)
            return True

    def hasValidEntryForDestination(self, destination: str) -> bool:
        entry = self.getEntry(destination)
        if entry is not None and entry.active:
            #self.logger.debug(entry.__dict__)
            return True

    def updateEntryWithDestination(self,destinationAdress: str):
        if not self.hasEntryForDestination(destinationAdress):
            self.logger.debug("Updating Route to "+destinationAdress)
            newRoute = Route()
            newRoute.isDestinationSequenceNumberValid = False
            newRoute.destinationSequenceNumber = 0
            newRoute.destinationAdress = destinationAdress
            newRoute.lifetime = int(time()*1000)+Constants.ACTIVE_ROUTE_TIMEOUT 
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
        newRoute.lifetime = max(currentLifetime, int(time()*1000)+ 2*Constants.NET_TRAVERSAL_TIME - 2*rreq.hopCount* Constants.NODE_TRAVERSAL_TIME)
        newRoute.nextHop = rreq.previousHop
        newRoute.hopCount = rreq.hopCount
        newRoute.active = True
        if oldRoute is None or self.isUpdatedNeeded(oldRoute,newRoute):
            self.updateEntry(newRoute)
