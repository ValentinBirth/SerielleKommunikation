from cmd import Cmd
from SerComClient import SerCom
import logging
 
class MainPrompt(Cmd):
    logging.basicConfig(level=logging.ERROR)

    logger = logging.getLogger(__name__)
    prompt = "sc> "
    intro = "Welcome! Type ? to list commands"
    client = SerCom()
 
    def do_exit(self, inp):
        """Exit the application. Shorthand: x q Ctrl-D."""
        print("Bye")
        try:
            self.client.exit()
        except Exception as err:
            self.logger.exception(err)
        return True
 
    def do_setUp(self, inp):
        """Configurate and start serial connection"""
        self.client.setUp()

    def do_sendCMD(self, inp):
        """Sends commands to serial Port"""
        self.client.write(inp)

    def do_send(self, inp):
        """Sends Message through LORA Module"""
        adress, msg = inp.split(" ")
        self.client.send(adress,msg)

    def do_queue(self,inp):
        """Prints content of queues for debugging"""
        if inp == "input":
            print(list(self.client.inputQueue.queue))
            return
        if inp == "output":
            print(list(self.client.outputQueue.queue))
            return

    def do_process(self, inp):
        print(self.client.inProcessing)
 
    def default(self, inp):
        if inp == 'x' or inp == 'q':
            return self.do_exit(inp)
        print("Default: {}".format(inp))

    do_EOF = do_exit
 
if __name__ == '__main__':
    MainPrompt().cmdloop()