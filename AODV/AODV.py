import base64
import bitstring
from time import time, sleep
from queue import Queue
from Model import UserData, RouteReply, RouteRequest, RoutingTable
from Constant import *
import logging
import threading

# TODO
# implement startup/reboot sequence
# reverse Route not established correctly
# Userdata encoding not working

logging.basicConfig(level=logging.DEBUG)
class AODV:
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

    def processRREQ(self, rreq: RouteRequest):
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
        self.logger.debug(rrep.__dict__)
        #self.routingTable.updateEntryWithDestination(rrep.previousHop)
        rrep.incrementHopCount()
        self.routingTable.updateEntryWithRREP(rrep)
        reverseRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
        if reverseRoute is not None:
            self.logger.debug("Process RREP RRTE: "+str(reverseRoute))
            reverseRoute.lifetime = max(reverseRoute.lifetime,int(time()*1000)+ACTIVE_ROUTE_TIMEOUT)
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
            rrep.lifetime = MY_ROUTE_TIMEOUT
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
        self.logger.error("RREP could not be sent")

    def checkForResponse(self):
        while True:
            with self.userDataBufferLock:
                if len(self.userDataBuffer) > 0:
                    for userData in self.userDataBuffer:
                        waitingTime = NET_TRAVERSAL_TIME
                        if userData.numRetries > RREQ_RETRIES:
                            self.userDataBuffer.remove(userData)
                            self.logger.error("Destimation "+userData.destinationAdress +" unreachable")
                        while userData.numRetries <= RREQ_RETRIES:
                            if self.routingTable.hasValidEntryForDestination(userData.destinationAdress):
                                self.send(self.routingTable.getEntry(userData.destinationAdress).nextHop,userData.encode())
                                continue
                            sleep(waitingTime)
                            userData.numRetries +=1
                            self.generateRREQ(userData.destinationAdress,True,0)
                            waitingTime = 2^userData.numRetries*NET_TRAVERSAL_TIME
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
        self.logger.debug("Parsed: "+payload+" from: "+addrStr)
        #payloadMatch = re.match("^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",payload)# check for BASE64 String
        #if payloadMatch is None:
        #    self.logger.error("Payload not BASE64 encoded: "+payload)
        #    return
        type = self.getPackageType(payload)
        if type == 0:
            package = UserData()
            self.logger.debug("Recieved User Data from "+addrStr)
            package.decode(payload)
            package.previousHop = addrStr
            self.processUD(package)
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

    def checkRREQBuffer(self):
        while True:
            with self.rreqBufferLock:
                if len(self.rreqBuffer) > 0:
                    for entry in self.rreqBuffer:
                        entryTimeStamp = self.rreqBuffer[entry]
                        entryTimeStamp += PATH_DISCOVERY_TIME
                        timestampMS = int(time()*1000)
                        if entryTimeStamp - timestampMS < 0:
                            self.rreqBuffer.pop(entry)
            sleep(PATH_DISCOVERY_TIME)