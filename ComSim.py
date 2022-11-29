import re
import serial.tools.list_ports, serial
import time
from datetime import datetime
import logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
#Config String: AT+CFG=433920000,5,3,12,4,1,0,0,0,0,4000,8,8

# REGEX DO CMD: AT\+[A-Z]{2,4}
# REGEX GET CMD: AT\+[A-Z]{2,4}\?
# REGEX SET CMD: AT\+[A-Z]{2,4}\=[A-Z0-9,]+

class ATSIM:
    ver = "V0.1"
    rx = False
    rssi = -63
    cfg = ""
    addr = "0015"
    dest = "FFFF"
    port = ""
    errCmd = "ERR:CMD"
    msgErrCPUBusy = "ERR:CPU_BUSY"
    msgErrRFBusy = "ERR:RF_BUSY"
    msgErrPara = "ERR:PARA"
    msgErrSymbl = "ERR:SYMBLE"
    msgOk = "AT+OK"
    msgSending = "AT, Sending"
    msgSended = "AT, Send"

    def getVer(self):
        return "AT, "+ self.ver +", OK"

    def rx(self):
        self.rx = True
        return self.msgOk
    
    def getRSSI(self):
        return "AT, "+ format(self.rssi, "04") +", OK"

    def getAddr(self):
        return "AT, "+ self.addr +", OK"
    
    def getDest(self):
        return "AT, "+ self.dest +", OK"

    def setAddr(self, param):
        paramMatch = re.fullmatch("[0-9A-F]{4}",param)
        if paramMatch == None:
            return self.msgErrPara
        else:
            paramStr = paramMatch.group()
            self.addr = paramStr
            return self.msgOk
    
    def setDest(self, param):
        paramMatch = re.fullmatch("[0-9A-F]{4}",param)
        if paramMatch == None:
            return self.msgErrPara
        else:
            paramStr = paramMatch.group()
            self.dest = paramStr
            return self.msgOk
    
    def setCFG(self, param):
        paramMatch = re.fullmatch("[0-9,]+",param)
        if paramMatch == None:
            return self.msgErrPara
        else:
            paramStr = paramMatch.group()
            paramList = paramStr.split(",")
            paramListInt = [int(x) for x in paramList]
            if len(paramListInt) != 12:
                return self.msgErrPara
            if paramListInt[0] < 410000000 | paramListInt[0] > 470000000:
                return self.msgErrPara
            if paramListInt[1] < 5 | paramListInt[0] > 20:
                return self.msgErrPara
            if paramListInt[2] < 0 | paramListInt[0] > 9:
                return self.msgErrPara
            if paramListInt[3] < 6 | paramListInt[0] > 12:
                return self.msgErrPara
            if paramListInt[4] < 1 | paramListInt[0] > 4:
                return self.msgErrPara
            if paramListInt[5] < 0 | paramListInt[0] > 1:
                return self.msgErrPara
            if paramListInt[6] < 0 | paramListInt[0] > 1:
                return self.msgErrPara
            if paramListInt[7] < 0 | paramListInt[0] > 1:
                return self.msgErrPara
            if paramListInt[8] < 0 | paramListInt[0] > 1:
                return self.msgErrPara
            if paramListInt[9] < 1 | paramListInt[0] > 65535:
                return self.msgErrPara
            if paramListInt[10] < 5 | paramListInt[0] > 255:
                return self.msgErrPara
            if paramListInt[11] < 4 | paramListInt[0] > 65535:
                return self.msgErrPara
            self.cfg = paramStr
            return self.msgOk

    def send(self, param):
        global ser
        paramMatch = re.fullmatch("[0-9]+",param)
        if paramMatch == None:
            return self.msgErrPara
        else:
            paramInt = int(paramMatch.group())
            if paramInt < 1 | paramInt > 250:
                return self.msgErrPara
            else:
                input = ser.read(paramInt)
                print("<"+str(datetime.now())+" sending >"+str(input))
                ser.flushInput()
                time.sleep(1)
                write(self.msgSending)
                time.sleep(1)
                write(self.msgSended)
            return "LR, "+self.addr+", "+str(format(len(input), '02x'))+", "+input.decode("utf-8")

    def parseInput(self,input):
        if input == "AT":
            write(self.msgOk)
            return
        
        #Check for do commands
        potentialMatch = re.fullmatch("AT\+[A-Z]{2,4}",input)
        if potentialMatch != None:
            cmdStr = potentialMatch.group().split("+")[1]
            if cmdStr == "RST":
                # implement method
                write(self.rst())
                return
            elif cmdStr == "VER":
                write(self.getVer())
                return
            elif cmdStr == "RX":
                write(self.rx())
                return
            elif cmdStr == "SAVE":
                # what does save do ?
                return
        
        # Check for get commands
        potentialMatch = re.fullmatch("AT\+[A-Z]{2,4}\?",input)
        if potentialMatch != None:
            cmdStr = potentialMatch.group().split("+")[1].replace("?","")
            if cmdStr == "RSSI":
                write(self.getRSSI())
                return
            elif cmdStr == "ADDR":
                write(self.getAddr())
                return
            elif cmdStr == "DEST":
                write(self.getDest())
                return
            
        # Check for set commands
        potentialMatch = re.fullmatch("AT\+[A-Z]{2,4}\=[A-Z0-9,]+",input)
        if potentialMatch != None:
            cmdMatch = potentialMatch.group().split("+")[1]
            cmdList = cmdMatch.split("=")
            cmdStr = cmdList[0]
            param = cmdList[1]
            if cmdStr == "ADDR":
                write(self.setAddr(param))
                return
            elif cmdStr == "DEST":
                write(self.setDest(param))
                return
            elif cmdStr == "CFG":
                write(self.setCFG(param))
                return
            elif cmdStr == "SEND":
                write(self.send(param))
                return
        write(self.errCmd)
        return


atSim = ATSIM()

def exit():
    """ Cleanup and close the programm """
    try:
        ser.close()
    except Exception as err:
        logger.exception(err)
    print("\nProgramm ended")

def selectPort():
    ports = {}
    ports.clear()
    portList = serial.tools.list_ports.comports()

    for ListPortInfo in portList:
        ports[len(ports)+1] = ListPortInfo
    
    msg = "Choose Port: \n"
    for key in ports:
        keyStr = str(key)
        value = ports[key]
        valueStr = str(value)
        msg = msg+keyStr+": "+valueStr+"\n"
    msg = msg + str(len(ports)+1)+": Manual Input \n"
    try:
        return str(ports[int(input(msg))].name)
    except KeyboardInterrupt:
        exit()
    except KeyError:
        return input("Manual Input: ")

def write(msg):
    """ Helper Method to write to COM Port"""
    msg.strip()
    msg = msg+"\r\n"
    global ser
    ser.write(msg.encode("utf-8"))
    print("<"+str(datetime.now())+" To   "+ser.name+"> "+ msg.strip())

def main():
    try:
        global atSim
        atSim.port = selectPort()
        global ser
        ser = serial.Serial(atSim.port)
        try:
            while True:
                if ser.in_waiting > 0:
                    data = ser.readline()
                    time.sleep(0.1)
                    if len(data) > 0:
                        msg = data.decode("utf-8").strip()
                        print("<"+str(datetime.now())+" From "+ser.name+'> ', msg)
                        atSim.parseInput(msg)
                time.sleep(0.01)
        except Exception as err:
            logger.exception(err)
            pass
    except KeyboardInterrupt:
        exit()
    except serial.SerialException:
        print("Port not found")
        main()

if __name__ == '__main__':
    main()