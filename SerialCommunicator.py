from cmd import Cmd
import threading
from time import sleep
import time
import serial.tools.list_ports, serial

 
class MainPrompt(Cmd):
    prompt = 'sc> '
    intro = "Welcome! Type ? to list commands"
 
    def do_exit(self, inp):
        print("Bye")
        try:
            client.exit()
        except:
            print('')
        return True
    
    def help_exit(self):
        print('exit the application. Shorthand: x q Ctrl-D.')
 
    def do_config(self, inp):
        "Configurate serial connection"
        print("TEST")

    def do_getConfig(self, inp):
        "Get onfiguration"
        try:
            print("TEST")
        except:
            print("No configuration preset, use config first")

    def do_send(self, inp):
        "Sends agruments to serial Port"
        try:
            print("TEST")
        except:
            print("No configuration preset, use config first")
    
    def do_disconnect(self,inp):
        "Disconnects aktive connection"
 
    def default(self, inp):
        if inp == 'x' or inp == 'q':
            return self.do_exit(inp)
        print("Default: {}".format(inp))

    do_EOF = do_exit
    help_EOF = help_exit
 
if __name__ == '__main__':
    MainPrompt().cmdloop()