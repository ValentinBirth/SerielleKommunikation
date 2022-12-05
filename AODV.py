import base64
import bitstring
class AODV:
    routingTable = {}
    reverseRoutingTable = {}

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
    format = "int6=type, bool1=flagOne, bool1=flagTwo, bool1=flagThree, bool1=flagFour, bool1=flagFive, bool1=flagSix, int6=hopCount, int6=requestID, hex16=destinationAdress, int8=destinationSequence, hex16=originatorAdress ,int8=originatorSequence"

    def decode(self, msg: str):
        base64_bytes = msg.encode('ascii')
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