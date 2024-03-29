import threading
import serial.tools.list_ports, serial
import time
import re
from queue import Queue
from AODV.AODV import AODV
import logging

class SerCom():
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.inputQueue = Queue(maxsize=0)
        self.outputQueue = Queue(maxsize=0)
        self.protocoll = AODV(self.outputQueue)
        self.inProcessing = False
        self.connected = False
        self.ser = None

    def send(self, destinaion: str, msg: str):
        self.protocoll.sendUserData(destinaion,msg)

    def reading(self):
        """ If something is in the input buffer its put into the input queue """
        while self.connected:
            if self.ser.in_waiting > 0:
                data = self.ser.readline()
                try:
                    msg = data.decode("utf-8").strip()
                except Exception as err:
                    self.logger.error(str(err)+"Msg: "+msg)
                    continue
                msgMatch = re.match("AT,(OK|[0-9a-zA-Z.-]*(,OK)*)", msg) #cmd confirmation
                if msgMatch is not None:
                    match = msgMatch.group()
                    if "SENDING" not in match: # not a cmd confirmation but not filtered by regex
                        self.inProcessing = False
                msgMatch = re.match("AT *,*[0-9A-Z]{4}, *OK", msg) # adress of own module
                if msgMatch is not None:
                    match = msgMatch.group()
                    ownAdress = match.split(",")[1].strip()
                    self.protocoll.ownAdress = ownAdress
                    self.logger.debug("Own Adress: "+self.protocoll.ownAdress)
                msgMatch = re.match("ERR:[A-Z_]*", msg) # err confirmation
                if msgMatch is not None:
                    self.inProcessing = False
                    self.logger.error(msg)
                msgMatch = re.match("LR, ?[0-9A-F]{4}, ?[0-9A-F]{2}, ?", msg) #msg from other modules
                if msgMatch is not None:
                    try:
                        self.protocoll.parse(msg)
                    except UnicodeDecodeError as err:
                        self.logger.exception("Cant decode in UTF-8: "+str(msg))
                    except Exception as err:
                        self.logger.exception(err)
            time.sleep(0.01)

    def writing(self):
        """ If something is in the output buffer its written to the serial port """
        while self.connected:
            if self.outputQueue.qsize() > 0:
                if not self.inProcessing:
                    msg = str(self.outputQueue.get())
                    msg = msg.strip()+"\r\n"
                    self.ser.write(msg.encode("utf-8"))
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
        except serial.SerialException:
            self.logger.error("Serial Port could not be opened, please try again")
        self.connected = True
        self.readThread = threading.Thread(target=self.reading, daemon=True).start()
        self.writeThread = threading.Thread(target=self.writing, daemon=True).start()
        self.write("AT+DEST=FFFF")
        self.write("AT+ADDR?")
        self.write("AT+CFG=433920000,5,7,7,4,1,0,0,0,0,3000,8,4")
        self.write("AT+RX")
    
    def exit(self):
        self.connected = False
        if self.ser is not None:
            self.ser.close()