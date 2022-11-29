import threading
import serial.tools.list_ports, serial
import time
from datetime import datetime
import re
import logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

#Config String: AT+CFG=433920000,5,6,10,4,1,0,0,0,0,3000,8,4

knownHost = []

class readingThread(threading.Thread):
    def __init__(self, threadID, name):
      threading.Thread.__init__(self)
      self._stopevent = threading.Event()
      self.threadID = threadID
      self.name = name

    def searchAndSaveAddr(self,msg):
        global knownHost
        msgMatch = re.match("LR, ?[0-9A-F]{4}, ?[0-9A-F]{2}, ?", msg)
        if msgMatch != None:
            msg = msgMatch.group()
            addrStr = msg.split(",")[1].strip()
            if addrStr not in knownHost:
                knownHost.append(addrStr)
            print(knownHost)


    def run(self):
        """ If something is in the input buffer its printed to the prompt """
        try:
            while not self._stopevent.is_set():
                if ser.in_waiting > 0:
                    data = ser.readline()
                    if len(data) > 0:
                        print("<"+str(datetime.now())+" From "+ser.name+'>', data.decode("utf-8").strip())
                        self.searchAndSaveAddr(data.decode("utf-8").strip())
                time.sleep(0.01)
        except Exception as err:
            logger.exception(err)
    
    def join(self, timeout=None):
        """ Exit the reader thread """
        self._stopevent.set()
        threading.Thread.join(self, timeout)

def exit():
    """ Cleanup and close the programm """
    try:
        readThread.join()
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


def main():
    try:
        selectedPort = selectPort()
        global ser
        ser = serial.Serial(selectedPort)

        global readThread
        readThread = readingThread(1, "Reader1")
        readThread.start()

        while True:
            inputMsg = input()
            if inputMsg == "quit":
                break
            if inputMsg != "":
                inputMsg = inputMsg.strip()+"\r\n"
                print("<"+str(datetime.now())+" To   "+ser.name+"> "+inputMsg.strip())
                ser.write(inputMsg.encode("utf-8"))
            time.sleep(0.03)
        exit()
    except KeyboardInterrupt:
        exit()
    except serial.SerialException:
        print("Port not found")
        main()

if __name__ == '__main__':
    main()