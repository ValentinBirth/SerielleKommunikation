import threading
import serial.tools.list_ports, serial
import time
import re
from datetime import datetime
from AODV import AODV

#Config String: AT+CFG=433920000,5,6,10,4,1,0,0,0,0,3000,8,4

class SerCom():
    def __init__(self, protocol: AODV):
        self.protocol = protocol
    ser = None
    readThread = None
    knownHosts = []

    def reading(self):
        """ If something is in the input buffer its printed to the prompt """
        while self.connected:
            if self.ser.in_waiting > 0:
                data = self.ser.readline()
                if len(data) > 0:
                    msg = data.decode("utf-8").strip()
                    msgMatch = re.match("LR, ?[0-9A-F]{4}, ?[0-9A-F]{2}, ?", msg)
                    if msgMatch != None:
                        self.protocol.parse(msg)
                    else:
                        print("<"+datetime.now().strftime("%H:%M:%S.%f")+" From "+self.ser.name+'>', msg)
            time.sleep(0.01)

    def write(self,msg: str):
        if msg != "":
            msg = msg.strip()+"\r\n"
            self.ser.write(msg.encode("utf-8"))

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
    
    def exit(self):
        self.connected = False
        self.ser.close()