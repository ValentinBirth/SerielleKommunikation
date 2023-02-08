import base64
import bitstring
from time import time, sleep
from queue import Queue
import logging
import threading
import math
from . import Models
from . import Constants

# TODO
# implement startup/reboot sequence
# redo loggin with color coding etc.
class AODV:
    RREQ_RETRIES = int(2)
    def __init__(self, outputQueue: Queue):
        self.outputQueue = outputQueue
        self.routingTable = Models.RoutingTable()
        self.reverseRoutingTable = Models.RoutingTable()
        self.ownAdress = None
        self.sequenceNumber = 0
        self.requestID = 0
        self.rreqBuffer = {}
        self.userDataBuffer = []
        self.userDataBufferLock = threading.Lock()
        self.rreqBufferLock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.readThread = threading.Thread(target=self.checkForResponse, daemon=True)
        self.readThread.start()
        self.checkRREQTread = threading.Thread(target=self.checkRREQBuffer, daemon=True)
        self.checkRREQTread.start()

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

    def processRREQ(self, rreq: Models.RouteRequest):
        self.logger.debug(rreq.previousHop+" send: "+str(rreq))
        #self.routingTable.updateEntryWithDestination(rreq.previousHop)
        with self.rreqBufferLock:
            for entry in self.rreqBuffer:
                if (rreq.requestID,rreq.originatorAdress) == entry:
                    return
        rreq.incrementHopCount()
        self.reverseRoutingTable.updateEntryWithRREQ(rreq)
        self.generateRREP(rreq)
        
    
    def processRREP(self, rrep: Models.RouteReply):
        self.logger.debug(rrep.previousHop+" send: "+str(rrep))
        rrep.incrementHopCount()
        self.routingTable.updateEntryWithRREP(rrep)
        if rrep.originatorAdress == self.ownAdress:
            return
        reverseRoute = self.reverseRoutingTable.getEntry(rrep.originatorAdress)
        if reverseRoute is not None:
            self.logger.debug("Process RREP RRTE: "+str(reverseRoute))
            reverseRoute.lifetime = max(reverseRoute.lifetime,int(time()*1000)+Constants.ACTIVE_ROUTE_TIMEOUT)
            forwardRoute = self.routingTable.getEntry(rrep.destinationAdress)
            forwardRoute.precursers.append(reverseRoute.nextHop)
            nextHopRoute = self.routingTable.getEntry(reverseRoute.nextHop)
            if nextHopRoute is not None:
                nextHopRoute.precursers.append(rrep.originatorAdress)
            if rrep.originatorAdress != self.ownAdress:
                self.send(reverseRoute.nextHop,rrep.encode())
            return
        self.logger.error("No Reverse Route found for RREP")

    def processUD(self, ud: Models.UserData):
        if ud.destinationAdress != self.ownAdress:
            if not self.routingTable.hasValidEntryForDestination(ud.destinationAdress):
                self.generateRREQ(ud.destinationAdress,True,0)
                with self.userDataBufferLock:
                    self.userDataBuffer.append(ud)
                return
            forwardRoute = self.routingTable.getEntry(ud.destinationAdress)
            self.send(forwardRoute.nextHop,ud.encode())
            return
        print(">> "+ud.userData)

    def send(self, destinationAdress: str, payload: str):
        self.logger.debug("Sending: "+payload+" to: "+destinationAdress)
        msgLenght = len(payload)
        adressCMD = "AT+DEST="+destinationAdress
        sendCMD = "AT+SEND="+str(msgLenght)
        self.outputQueue.put(adressCMD)
        self.outputQueue.put(sendCMD)
        self.outputQueue.put(payload)

    def sendUserData(self, destination: str, data: str):
        userData = Models.UserData()
        userData.destinationAdress = destination
        userData.userData = data
        if self.routingTable.hasValidEntryForDestination(destination):
            self.send(self.routingTable.getEntry(destination).nextHop,userData.encode())
            return
        self.generateRREQ(userData.destinationAdress,True,0)
        with self.userDataBufferLock:
            self.userDataBuffer.append(userData)
            

    def generateRREP(self, rreq: Models.RouteRequest):
        rrep = Models.RouteReply()
        if rreq.destinationAdress == self.ownAdress:
            self.logger.debug("Generate RREP for "+rreq.destinationAdress+", i am destination")
            rrep.destinationAdress = self.ownAdress
            rrep.originatorAdress = rreq.originatorAdress
            rrep.destinationSequence = self.sequenceNumber
            rrep.hopCount = int(0)
            rrep.lifetime = Constants.MY_ROUTE_TIMEOUT
            self.incrementSequenceNumber()
            if not self.sequenceNumber == rreq.destinationSequence:
                self.decrementSequenceNumber()
            rrep.destinationSequence = self.sequenceNumber
            if rreq.previousHop != rreq.originatorAdress:
                self.send(rreq.previousHop, rrep.encode())
            else:
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
            self.logger.debug("Generate RREP for "+rreq.destinationAdress+" , route found")
            if rreq.previousHop != rreq.originatorAdress:
                self.send(rreq.previousHop, rrep.encode())
            else:
                self.send(rreq.originatorAdress, rrep.encode())
            return
        self.send("FFFF", rreq.encode())

    def checkForResponse(self):
        while True:
            with self.userDataBufferLock:
                if len(self.userDataBuffer) > 0:
                    for userData in self.userDataBuffer:
                        userData: Models.UserData
                        waitingTime = Constants.NET_TRAVERSAL_TIME
                        if userData.numRetries >= AODV.RREQ_RETRIES:
                            self.userDataBuffer.remove(userData)
                            self.logger.error("Destimation "+userData.destinationAdress +" unreachable")
                        while userData.numRetries <= AODV.RREQ_RETRIES:
                            if self.routingTable.hasValidEntryForDestination(userData.destinationAdress):
                                try:
                                    self.userDataBuffer.remove(userData)
                                except Exception:
                                    pass
                                self.send(self.routingTable.getEntry(userData.destinationAdress).nextHop,userData.encode())
                                break
                            userData.numRetries = userData.numRetries+1
                            sleep(waitingTime/1000)
                            self.generateRREQ(userData.destinationAdress,True,0)
                            waitingTime = math.pow(2,userData.numRetries)*Constants.NET_TRAVERSAL_TIME
            sleep(Constants.NET_TRAVERSAL_TIME/1000)

    def generateRREQ(self, destinationAdress: str,isSequenceNumberUnknown: bool, destinationSequenceNumber: str):
        self.logger.debug("Generating RREQ to "+destinationAdress)
        rreq = Models.RouteRequest()
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
        type = self.getPackageType(payload)
        if type == 0:
            package = Models.UserData()
            package.decode(payload)
            package.previousHop = addrStr
            self.processUD(package)
        if type == 1:
            package = Models.RouteRequest()
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREQ(package)
        if type == 2:
            package = Models.RouteReply()
            package.decode(payload)
            package.previousHop = addrStr
            self.processRREP(package)
        

    def getPackageType(self, msg: str):
        base64_bytes = msg
        try:
            message_bytes = base64.b64decode(base64_bytes)
            byteArray = bitstring.BitArray(bytes=message_bytes)
            type = byteArray[:6].uint
            return type
        except Exception as err:
            self.logger.error("Package type could not be identified Msg: "+msg)

    def checkRREQBuffer(self):
        while True:
            with self.rreqBufferLock:
                if len(self.rreqBuffer) > 0:
                    for entry in list(self.rreqBuffer):
                        entryTimeStamp = self.rreqBuffer[entry]
                        entryTimeStamp += Constants.PATH_DISCOVERY_TIME
                        timestampMS = int(time()*1000)
                        if entryTimeStamp - timestampMS < 0:
                            self.rreqBuffer.pop(entry)
            sleep(Constants.PATH_DISCOVERY_TIME/1000)