from cmd import Cmd
from SerComClient import SerCom
from tabulate import tabulate
import logging
import logging.config
import yaml
 
class MainPrompt(Cmd):
    with open('logconf.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)

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
        args= inp.split(" ")
        if len(args) != 2:
            print("Wrong number of arguments, needs 2")
            return
        adress = args[0]
        msg = args[1]
        self.client.send(adress,msg)

    def do_queue(self,inp):
        """Prints content of queues for debugging"""
        if inp == "input":
            print(list(self.client.inputQueue.queue))
            return
        if inp == "output":
            print(list(self.client.outputQueue.queue))
            return
    
    def do_table(self, inp):
        """Prints Routingtable"""
        if inp == "rt":
            print(tabulate(self.client.protocoll.routingTable.getTable(), tablefmt="plain"))
            return
        if inp == "rrt":
            print(tabulate(self.client.protocoll.reverseRoutingTable.getTable(), tablefmt="plain"))
            return

    def do_udBuffer(self, inp):
        """ Prints User Data Buffer"""
        print(self.client.protocoll.getUserDataBuffer())

    def do_process(self, inp):
        print(self.client.inProcessing)
 
    def default(self, inp):
        if inp == 'x' or inp == 'q':
            return self.do_exit(inp)
        print("Default: {}".format(inp))

    do_EOF = do_exit
 
if __name__ == '__main__':
    MainPrompt().cmdloop()