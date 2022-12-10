import threading
import serial.tools.list_ports, serial
import time
import re
from queue import Queue
from AODV import AODV
import logging

class SerCom():
    def __init__(self, inputQueue: Queue, outputQueue: Queue):
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue
    logging.basicConfig(level=logging.DEBUG)

    logger = logging.getLogger(__name__)
    inProcessing = False
    connected = False

    def send(self, msg):
        msgLenght = len(msg)
        cmd = "AT+SEND="+str(msgLenght)
        self.write(cmd)
        self.write(msg)
        

    def reading(self):
        """ If something is in the input buffer its put into the input queue """
        while self.connected:
            if self.ser.in_waiting > 0:
                data = self.ser.readline()
                msg = data.decode("ascii").strip()
                msgMatch = re.match("AT,(OK|[0-9a-zA-Z.-]*(,OK)*)", msg) #cmd confirmation
                if msgMatch != None:
                    match = msgMatch.group()
                    if "SENDING" not in match: # not a cmd confirmation but not filtered by regex
                        self.inProcessing = False
                msgMatch = re.match("LR, ?[0-9A-F]{4}, ?[0-9A-F]{2}, ?", msg) #msg from other modules
                if msgMatch != None:
                    self.inputQueue.put(msg)
                    self.logger.debug(msg)
            time.sleep(0.01)

    def writing(self):
        """ If something is in the output buffer its written to the serial port """
        while self.connected:
            if self.outputQueue.qsize() > 0:
                if not self.inProcessing:
                    msg = str(self.outputQueue.get())
                    msg = msg.strip()+"\r\n"
                    self.ser.write(msg.encode("ascii"))
                    self.inProcessing = True
            time.sleep(0.01)

    def write(self,msg: str):
        if self.connected:
            self.outputQueue.put(msg)
        else:
            print("No Port open, use setUp first")

    def setUp(self):
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
            inputPort = str(ports[int(input(msg))].name)
            self.ser = serial.Serial(inputPort)
        except KeyError:
            self.ser = serial.Serial(input("Manual Input: "))
        self.connected = True
        self.readThread = threading.Thread(target=self.reading, daemon=True).start()
        self.writeThread = threading.Thread(target=self.writing, daemon=True).start()
        self.write("AT+DEST=FFFF")
        self.write("AT+CFG=433920000,5,6,10,4,1,0,0,0,0,3000,8,4")
        self.write("AT+RX")
    
    def exit(self):
        self.connected = False
        self.ser.close()