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

    def do_sendLow(self, inp):
        """Sends agruments to serial Port"""
        try:
            self.client.write(inp)
        except:
            print("No configuration preset, use config first")

    def do_send(self, inp):
        """Sends Message through LORA Module"""
        self.client.send(inp)
 
    def default(self, inp):
        if inp == 'x' or inp == 'q':
            return self.do_exit(inp)
        print("Default: {}".format(inp))

    do_EOF = do_exit
 
if __name__ == '__main__':
    MainPrompt().cmdloop()