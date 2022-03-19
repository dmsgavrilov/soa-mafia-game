import threading


import grpc

import proto.chat_pb2 as chat
import proto.chat_pb2_grpc as rpc

from commands import client_commands

HOST = 'localhost'
PORT = 5000


class Client:

    def __init__(self, nickname: str):
        self.nickname = nickname
        channel = grpc.insecure_channel(HOST + ':' + str(PORT))
        self.conn = rpc.ChatServerStub(channel)
        self.id = self.conn.Connect(chat.Connection(nickname=nickname)).member_id
        threading.Thread(target=self.listen_for_messages, daemon=True).start()
        self.write()

    def message_handler(self, note):
        if self.id == note.member_id or (note.to and self.id not in note.to):
            return
        if note.name:
            print(f"{note.name}: {note.message}")
        else:
            print(f"{note.message}")

    def listen_for_messages(self):
        for note in self.conn.ChatStream(chat.Empty()):
            self.message_handler(note)

    def write(self):
        while True:
            message = input()
            if message:
                n = chat.Note(
                    name=self.nickname, member_id=self.id, message=message
                )
                self.conn.SendNote(n)
                if message == client_commands.LEAVE:
                    break


if __name__ == '__main__':
    nickname = input("Enter your nickname:\n")
    c = Client(nickname)
