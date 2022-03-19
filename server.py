from concurrent import futures
from collections import Counter
import time
import random
import threading

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
        self._status = None
        self._role = None

    def prepare(self, role):
        self._role = role
        self._status = "alive"

    def dead(self):
        self._status = "dead"
        self._role = "spirit"

    @property
    def nickname(self):
        return self._nickname

    @property
    def member_id(self):
        return self._member_id

    @property
    def role(self):
        return self._role

    @property
    def status(self):
        return self._status


class ChatServer(rpc.ChatServerServicer):

    def __init__(self, size):
        self.members = {}
        self.chats = []
        self.size = size

        # Game Section
        self._game_running = False
        self._voting = []
        self._voted = []
        self._active_role = None
        self._daytime = None

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
        if len(self.members) == self.size:
            threading.Thread(target=self.start_game).start()
        return chat.ConnectionReply(member_id=m.member_id)

    def serialize_members(self, m):
        members_text = "ID\tNAME"
        if self._game_running:
            members_text += "\tROLE\tSTATUS"
        members_text += "\n"
        for member in self.members.values():
            members_text += f"{member.member_id}\t{member.nickname}"
            if self._game_running:
                if m.status == "alive":
                    members_text += f"\t???\t{member.status}"
                else:
                    members_text += f"\t{member.role}\t{member.status}"
            if member.member_id == m.member_id:
                members_text += " << YOU"
            members_text += "\n"
        return members_text

    def members_with_role(self, role, self_id):
        mafias_ids = []
        for member in self.members.values():
            if member.role == role and member.member_id != self_id:
                mafias_ids.append(member.member_id)
        if not mafias_ids:
            mafias_ids = [-1]
        return mafias_ids

    def members_with_status(self, status, self_id):
        mafias_ids = []
        for member in self.members.values():
            if member.status == status and member.member_id != self_id:
                mafias_ids.append(member.member_id)
        if not mafias_ids:
            mafias_ids = [-1]
        return mafias_ids

    def message_handler(self, note: chat.Note):
        if note.message.startswith(client_commands.MEMBERS):
            self.send_message(self.serialize_members(self.members[note.member_id]), note.member_id)
        elif note.message.startswith(client_commands.LEAVE):
            left_member = self.members[note.member_id]
            self.members.pop(note.member_id)
            if self._game_running:
                self.set_default()
                self.send_message("GAME STOPPED")
            self.send_message(f"{left_member.nickname} left")
        elif note.message.startswith(client_commands.HELP):
            self.send_message(client_commands.COMMANDS_LIST, note.member_id)
        elif note.message.startswith(client_commands.SELF):
            if self._game_running:
                self.send_message(f"YOU ARE {self.members[note.member_id].role}", note.member_id)
        elif note.message.startswith(client_commands.READY):
            if self._game_running:
                return
            if note.member_id not in self._voted:
                self._voted.append(note.member_id)
                self.send_message(f"{self.members[note.member_id].nickaname} is ready to start game")
        elif note.message.startswith(client_commands.KILL):
            if self._game_running:
                member = self.members[note.member_id]
                if member.role == self._active_role \
                        and member.member_id not in self._voted \
                        and member.status == "alive":
                    try:
                        victim_id = int(note.message.split(" ")[1])
                        self._voted.append(member.member_id)
                        self._voting.append(victim_id)
                        self.send_message(
                            f"{member.nickname} is voted for {self.members[victim_id].nickname}",
                            self.members_with_role(member.role, member.member_id)
                        )
                    except:
                        self.send_message("INCORRECT VICTIM ID", note.member_id)
        elif note.message.startswith(client_commands.EXECUTE):
            if self._game_running:
                member = self.members[note.member_id]
                if self._daytime == "day" and note.member_id not in self._voted and member.status == "alive":
                    try:
                        victim_id = int(note.message.split(" ")[1])
                        self._voted.append(note.member_id)
                        self._voting.append(victim_id)
                        self.send_message(f"{member.nickname} is voted for {self.members[victim_id].nickname}")
                    except:
                        self.send_message("INCORRECT VICTIM ID", note.member_id)
        elif note.message.startswith(client_commands.SKIP):
            if self._game_running:
                member = self.members[note.member_id]
                if self._daytime == "day" and note.member_id not in self._voted and member.status == "alive":
                    try:
                        self._voted.append(note.member_id)
                        self._voting.append(0)
                        self.send_message(f"{member.nickname} is voted for skipping execution")
                    except:
                        self.send_message("INCORRECT VICTIM ID", note.member_id)
        elif note.message.startswith(client_commands.VERIFY):
            if self._game_running:
                if self.members[note.member_id].role == self._active_role \
                        and self._active_role == "cherif" \
                        and note.member_id not in self._voted \
                        and self.members[note.member_id].status == "alive":
                    victim_id = int(note.message.split(" ")[1])
                    victim = self.members[victim_id]
                    self.send_message(f"{victim.nickname} IS {victim.role}", note.member_id)
        elif self._game_running:
            member = self.members[note.member_id]
            if self._daytime == "night" and member.role != "citizen":
                n = chat.Note(
                    member_id=note.member_id, name=note.name, message=note.message,
                    to=self.members_with_role(member.role, member.member_id)
                )
                self.chats.append(n)
            elif self._daytime == "day":
                n = chat.Note(
                    member_id=note.member_id, name=note.name, message=note.message,
                    to=self.members_with_status(member.status, member.member_id)
                )
                self.chats.append(n)
        else:
            self.chats.append(note)

    def send_message(self, text, to=None):
        if type(to) != list and to:
            to = [to]
        n = chat.Note(message=text, to=to)
        self.chats.append(n)

    def start_game(self):
        self._game_running = True
        self._voted = []
        distribution = []
        mafias_count = 1 + int((self.size - 4) / 2)
        for i in range(mafias_count):
            distribution.append("mafia")
        distribution.append("cherif")
        citizens_count = self.size - mafias_count - 1
        for i in range(citizens_count):
            distribution.append("citizen")
        random.shuffle(distribution)

        count = {
            "mafia": mafias_count,
            "cherif": 1,
            "citizen": citizens_count
        }
        wait_mafia = mafias_count * 15
        wait_cherif = 15
        wait_all = 15 * self.size

        self.send_message("STARTING GAME")
        self.send_message(".\n" * 5)
        for i, member in enumerate(self.members.values()):
            member.prepare(distribution[i])
            self.send_message(f"YOU ARE {member.role}", member.member_id)

        self.send_message("\nINSIDIOUS MAFIA STARTED UP IN THE CITY. YOU MUST FIND OUT WHO IT IS!\n")
        self.send_message("IF YOU DON'T KNOW COMMANDS TYPE '/help' TO SEE LIST OF COMMANDS\n")

        time.sleep(1)
        while count["mafia"] < count["citizen"] + count["cherif"] and count["mafia"] != 0:
            self._daytime = "night"
            self.send_message("THE CITY FALLS ASLEEP, BUT...")
            self._active_role = "mafia"
            self.send_message("MAFIA IS DOING ITS DARK DEEDS")
            time.sleep(wait_mafia)
            mafia_killed = None
            if self._voting:
                v = Counter(self._voting)
                mafia_killed = list(v.keys())[0]
                self._voting = []
                self._voted = []
            self.send_message("\nMAFIA FINISHED\n")
            time.sleep(1)

            self.send_message("CHERIF WOKE UP TO FIND MAFIA")
            self._active_role = "cherif"
            time.sleep(wait_cherif)
            cherif_killed = None
            if self._voting:
                cherif_killed = self._voting[0]
                self._voting = []
                self._voted = []
            self.send_message("CHERIF FINISHED")
            time.sleep(1)

            dead_list = "TONIGHT WE LOST:\n"
            if mafia_killed:
                if self.members[mafia_killed].status == "alive":
                    role = self.members[mafia_killed].role
                    self.members[mafia_killed].dead()
                    count[role] -= 1
                    dead_list += f" - {self.members[mafia_killed].nickname}\n"
            if cherif_killed:
                if self.members[cherif_killed].status == "alive":
                    role = self.members[cherif_killed].role
                    self.members[cherif_killed].dead()
                    count[role] -= 1
                    dead_list += f" - {self.members[cherif_killed].nickname}\n"

            self._active_role = None
            self._daytime = "day"
            self.send_message("\nGOOD MORNING\n")
            self.send_message(dead_list)
            if count["mafia"] >= count["citizen"] + count["cherif"] or count["mafia"] == 0:
                self.set_default()
                break
            self.send_message("IT'S TIME TO DECIDE")
            time.sleep(wait_all)
            executed = None
            if self._voting:
                v = Counter(self._voting)
                executed = list(v.keys())[0]
                self._voting = []
                self._voted = []
            if executed:
                if self.members[executed].status == "alive":
                    role = self.members[executed].role
                    self.members[executed].dead()
                    count[role] -= 1
                    self.send_message(f"{self.members[executed].nickname} WAS EXECUTED")
            else:
                self.send_message("VOTING WAS SKIPPED")
        if count["mafia"]:
            self.send_message("\nMAFIA WON!\n")
        else:
            self.send_message("\nCITIZENS WON!\n")
        self.set_default()

    def set_default(self):
        self._daytime = None
        self._voted = []
        self._voting = []
        self._active_role = None
        self._daytime = None


if __name__ == '__main__':
    port = 5000
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    try:
        server_size = max(4, int(input("Enter server size (min is 4):\n")))
    except:
        server_size = 4
    rpc.add_ChatServerServicer_to_server(ChatServer(server_size), server)
    print('Starting server. Listening...')
    server.add_insecure_port('[::]:' + str(port))
    server.start()
    server.wait_for_termination()
