import socket
import time
import threading

from commands import client_commands, server_commands


class Client:
    def __init__(self, host, port, nickname):
        self.nickname = nickname

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.closed = False
        self.room_id = None

        threading.Thread(target=self.receive).start()
        threading.Thread(target=self.write).start()

    def receive(self):
        while not self.closed:
            try:
                data = self.sock.recv(1024)
                message = data.decode("utf-8")
                if message == server_commands.NICKNAME:
                    self.sock.send(self.nickname.encode("utf-8"))
                else:
                    print(message)
            except:
                time.sleep(0.5)
                self.leave()

    def send(self, message):
        self.sock.send(message.encode("utf-8"))

    def write(self):
        while not self.closed:
            try:
                msg_text = input()
                if msg_text:
                    self.send(msg_text)
                    if msg_text == client_commands.LEAVE:
                        time.sleep(0.5)
                        self.leave()

            except:
                self.leave()

    def leave(self):
        self.closed = True
        self.sock.close()


# host = input("Enter IP-address of the server:\n")
# port = int(input("Enter port of the server:\n"))
# nickname = input("Enter your nickname:\n")

host = "127.0.0.1"
port = 5000
nickname = "dima"

client = Client(host, port, nickname)
