from concurrent import futures

import grpc
import proto.chat_pb2 as chat
import proto.chat_pb2_grpc as rpc

from commands import client_commands


class Member:
    _counter = 0

    def __init__(self, nickname):
        Member._counter += 1
        self._nickname = nickname
        self._member_id = self._counter

    @property
    def nickname(self):
        return self._nickname

    @property
    def member_id(self):
        return self._member_id


class ChatServer(rpc.ChatServerServicer):

    def __init__(self):
        self.members = {}
        self.chats = []

    def ChatStream(self, request_iterator, context):
        lastindex = 0
        while True:
            while len(self.chats) > lastindex:
                n = self.chats[lastindex]
                lastindex += 1
                yield n

    def SendNote(self, request: chat.Note, context):
        self.message_handler(request)
        return chat.Empty()

    def Connect(self, request: chat.Connection, context):
        m = Member(request.nickname)
        self.members[m.member_id] = m
        n = chat.Note(message=f"{m.nickname} joined!")
        self.chats.append(n)
        return chat.ConnectionReply(member_id=m.member_id)

    def serialize_members(self):
        members_text = "ID\tNAME\n"
        for member_id, member in self.members.items():
            members_text += f"{member.member_id}\t{member.nickname}\n"
        return members_text

    def message_handler(self, note: chat.Note):
        if note.message.startswith(client_commands.MEMBERS):
            n = chat.Note(message=self.serialize_members(), to=[note.member_id])
            self.chats.append(n)
        if note.message.startswith(client_commands.LEAVE):
            left_member = self.members[note.member_id]
            n = chat.Note(message=f"{left_member.nickname} left")
            self.chats.append(n)
        else:
            self.chats.append(note)


if __name__ == '__main__':
    port = 5000
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc.add_ChatServerServicer_to_server(ChatServer(), server)
    print('Starting server. Listening...')
    server.add_insecure_port('[::]:' + str(port))
    server.start()
    server.wait_for_termination()
