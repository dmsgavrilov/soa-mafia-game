import socket
import time
import threading
from random import shuffle
from collections import Counter

from commands import server_commands, client_commands

HOST = '127.0.0.1'
PORT = 5000


class Member:
    _counter = 0

    def __init__(self, connection, address, nickname):
        Member._counter += 1
        self.id = self._counter
        self._connection = connection
        self._address = address
        self._nickname = nickname
        self._room_id = None

    def set_room(self, room_id):
        self._room_id = room_id

    def disconnect(self):
        self._connection.close()

    def send(self, message):
        self._connection.send(message.encode("utf-8"))

    def __eq__(self, other):
        return self.connection == other.connection

    @property
    def connection(self):
        return self._connection

    @property
    def address(self):
        return self._address

    @property
    def nickname(self):
        return self._nickname

    @property
    def room_id(self):
        return self._room_id


class Player:
    def __init__(self, role, member, player_id):
        self.player_id = player_id
        self._member = member
        self._role = role  # Citizen, Cherif, Mafia
        self._alive = True

    def died(self):
        self._alive = False

    @property
    def role(self):
        return self._role

    @property
    def alive(self):
        return self._alive

    @property
    def member(self):
        return self._member


class Game:
    def __init__(self):
        self.players = {}
        self.active = False
        self.daytime = None
        self.active_role = None
        self.voting = []
        self.voted = []

    def set_default(self):
        self.players = {}
        self.active = False
        self.daytime = None
        self.active_role = None
        self.voting = []
        self.voted = []

    def prepare(self, room):
        if room.size >= min(len(room.members), 4):
            self.players = self._distribute(room.members)
            self.active = True
            self.send_game_messages("\nINSIDIOUS MAFIA STARTED UP IN THE CITY. YOU MUST FIND OUT WHO IT IS!\n")
            time.sleep(1)
            for player in self.players.values():
                player.member.send(f"YOU ARE {player.role}!")
            return 1
        return 0

    def start(self):
        if not self.active:
            return
        count = {
            "mafia": 1 + int((len(self.players) - 4) / 2),
            "cherif": 1,
            "citizen": len(self.players) - int((len(self.players) - 4) / 2) - 2
        }
        time.sleep(1)
        while count["mafia"] < count["citizen"] + count["cherif"] and count["mafia"] != 0 and self.active:
            self.daytime = "night"
            self.active_role = "mafia"
            self.send_game_messages("MAFIA IS DOING ITS DARK DEEDS")
            time.sleep(30)
            mafia_killed = None
            if self.voting:
                v = Counter(self.voting)
                mafia_killed = list(v.keys())[0]
                self.voting = []
                self.voted = []
            self.send_game_messages("\nMAFIA FINISHED\n")
            time.sleep(1)

            self.send_game_messages("CHERIF WOKE UP TO FIND MAFIA")
            self.active_role = "cherif"
            time.sleep(30)
            cherif_killed = None
            if self.voting:
                cherif_killed = self.voting[0]
                self.voting = []
                self.voted = []
            self.send_game_messages("Cherif finished")
            time.sleep(1)

            dead_list = "TONIGHT WE LOST:\n"
            if mafia_killed:
                if self.players[mafia_killed].alive:
                    self.players[mafia_killed].died()
                    role = self.players[mafia_killed].role
                    count[role] -= 1
                    dead_list += f" - {self.players[mafia_killed].member.nickname}\n"
            if cherif_killed:
                if self.players[cherif_killed].alive:
                    self.players[cherif_killed].died()
                    role = self.players[cherif_killed].role
                    count[role] -= 1
                    dead_list += f" - {self.players[cherif_killed].member.nickname}\n"

            self.active_role = None
            self.daytime = "day"
            self.send_game_messages("\nGOOD MORNING\n")
            self.send_game_messages(dead_list)
            self.send_game_messages("IT'S TIME TO DECIDE")
            time.sleep(120)
            executed = None
            if self.voting:
                v = Counter(self.voting)
                executed = list(v.keys())[0]
                self.voting = []
                self.voted = []
            if executed:
                if self.players[executed].alive:
                    self.players[executed].died()
                    role = self.players[executed].role
                    count[role] -= 1
                    self.send_game_messages(f"{self.players[executed].member.nickname} WAS EXECUTED")
            else:
                self.send_game_messages("VOTING WAS SKIPPED")
        if count["mafia"]:
            self.send_game_messages("\nMAFIA WON!\n")
        else:
            self.send_game_messages("\nCITIZENS WON!\n")
        self.set_default()

    def send_game_messages(self, message):
        for player in self.players.values():
            player.member.send(message)

    def get_player(self, room_member):
        for player in self.players.values():
            if player.member == room_member:
                return player

    def _distribute(self, room_members):
        distribution = []
        mafias_count = 1 + int((len(room_members) - 4) / 2)
        for i in range(mafias_count):
            distribution.append("mafia")
        distribution.append("cherif")
        citizens_count = len(room_members) - mafias_count - 1
        for i in range(citizens_count):
            distribution.append("citizen")
        shuffle(distribution)
        return {i + 1: Player(distribution[i], room_members[i], i + 1) for i in range(len(distribution))}

    def exclude_player(self, member):
        for i, player in self.players:
            if player.member == member:
                self.players.pop(i)
                return


class Room:
    _counter = 0

    def __init__(self, title, admin):
        self._title = title
        Room._counter += 1
        self._room_id = self._counter
        self._admin = admin
        self._members = [admin]
        self._size = 4
        self._game = Game()

    def add_member(self, member):
        if member not in self._members:
            self._members.append(member)

    def exclude_member(self, member):
        self._members.remove(member)

    def remove_member(self, member):
        try:
            self._members.remove(member)
        except:
            pass

    def set_size(self, size):
        if size > max(len(self._members), 4):
            self._size = size
            return 1
        return 0

    def prepare_game(self):
        return self._game.prepare(self)

    def start_game(self):
        self._game.start()

    def is_admin(self, member):
        return self._admin == member

    def set_admin(self, member):
        self._admin = member

    @property
    def size(self):
        return self._size

    @property
    def room_id(self):
        return self._room_id

    @property
    def title(self):
        return self._title

    @property
    def admin(self):
        return self._admin

    @property
    def members(self):
        return self._members

    @property
    def game(self):
        return self._game


class Server:
    def __init__(self, host, port):
        self.rooms = {}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.server.bind((host, port))
        self.server.listen()
        self.accept_connections()

    def serialize_rooms(self):
        if not self.rooms:
            return ""
        rooms_txt = "ID\tTITLE\tMEMBERS\n"
        for room in self.rooms.values():
            if not room.game.active:
                rooms_txt += f"{room.room_id}\t{room.title}\t{len(room.members)} / {room.size}"
        return rooms_txt

    def serialize_members(self, room):
        members_text = "room_members:\n"
        for member in room.members:
            members_text += f" - {member.nickname} {member.address}\n"
        return members_text

    def serialize_players(self, room, self_player):
        players_text = "ID\tNICKNAME\tALIVE\tROLE\n"
        for player_id, player in room.game.players.items():
            players_text += f"{player_id}\t{player.member.nickname}\t{player.alive}"
            if not self_player.alive:
                players_text += f"\t{player.role}\n"
            else:
                players_text += f"\t???\n"
        return players_text

    def accept_connections(self):
        while True:
            conn, address = self.server.accept()
            print("Connected with {}".format(str(address)))

            conn.send(server_commands.NICKNAME.encode("utf-8"))
            nickname = conn.recv(1024).decode("utf-8")

            print("Nickname is {}".format(nickname))

            m = Member(conn, address, nickname)

            m.send("You can create room or connect to one that exists. Use commands:\n"
                   "/create_room {title} - to create room\n"
                   "/connect {room_id} - to connect to room\n"
                   "print /help to see all commands")
            m.send(self.serialize_rooms())

            threading.Thread(target=self.handle, args=(m,)).start()

    def handle_text(self, member, message):
        if message.startswith(client_commands.CREATE_ROOM):
            room_title = message.split(" ")[1]
            room = Room(room_title, member)
            member.set_room(room.room_id)
            self.rooms[room.room_id] = room
            member.send(f"Room '{room_title}' was created, room_id is {room.room_id}")

        elif message.startswith(client_commands.LEAVE):
            member.send("LEAVE")
            return 1

        elif message.startswith(client_commands.HELP):
            msg_text = "LIST OF COMMANDS:\n" \
                       "   /leave - to leave server\n" \
                       "   /members - list of room members\n" \
                       "   /create_room {title} - creates the room\n" \
                       "   /connect {room_id} - connects to the room\n" \
                       "   /set_size {size} - set size for room (for room admin)\n" \
                       "   /start_game - start game (for room admin)\n" \
                       "   /rooms - list of rooms\n" \
                       "   /players - list of players (only during game)\n" \
                       "   /me - shows your character (only during game)\n" \
                       "   /kill - kill players " \
                       "(only during game, available for cherif and mafia during night)\n" \
                       "   /verify {player_id} - shows role of the player " \
                       "(only during game, available for cherif during night)\n" \
                       "   /execute {player_id} - votes for executing player " \
                       "(only during game, available for citizens during day)\n" \
                       "   /skip - votes for skipping day without executing " \
                       "(only during game, available for citizens during day)\n"
            member.send(msg_text)

        elif message.startswith(client_commands.ROOMS):
            if not member.room_id:
                member.send(self.serialize_rooms())

        elif message.startswith(client_commands.CONNECT):
            room_to_connect = int(message.split(" ")[1])
            room = self.rooms.get(room_to_connect, None)
            if room:
                if not room.game.active:
                    if len(room.members) + 1 <= room.size:
                        room.add_member(member)
                        member.set_room(room_to_connect)
                        member.send("You joined the room")
                        self.broadcast(f"{member.nickname} joined!", member)
                    else:
                        member.send("Can't connect, room is full")
                else:
                    member.send("Game has already started")
            else:
                member.send("Room doesn't exist or room_id is not valid")

        elif message.startswith(client_commands.MEMBERS):
            if member.room_id:
                room = self.rooms[member.room_id]
                if not room.game.active:
                    member.send(self.serialize_members(room))
            else:
                member.send("You are not in room")

        elif message.startswith(client_commands.SET_SIZE):
            if member.room_id:
                size = int(message.split(" ")[1])
                room = self.rooms[member.room_id]
                if not room.game.active:
                    if room.is_admin(member):
                        ret = room.set_size(size)
                        if ret:
                            member.send(f"Room size was changed to {size}")
                        else:
                            member.send("Size is not valid")
                    else:
                        member.send("You don't have enough permissions")
            else:
                member.send("You are not in room")

        elif message.startswith(client_commands.START_GAME):
            if member.room_id:
                room = self.rooms[member.room_id]
                if not room.game.active:
                    if room.is_admin(member):
                        ret = room.prepare_game()
                        if ret:
                            threading.Thread(target=room.start_game).start()
                        else:
                            member.send("Something went wrong")
                else:
                    member.send("You don't have enough permissions")
            else:
                member.send("You are not in room")

        elif message.startswith(client_commands.PLAYERS):
            if member.room_id:
                room = self.rooms[member.room_id]
                if room.game.active:
                    member.send(self.serialize_players(room, room.game.get_player(member)))

        elif message.startswith(client_commands.KILL):
            if member.room_id:
                room = self.rooms[member.room_id]
                player = room.game.get_player(member)
                if room.game.active and room.game.daytime == "night" \
                   and room.game.active_role == player.role and player.alive:
                    player_id = int(message.split(" ")[1])
                    if player_id in room.game.players and member not in room.game.voted:
                        room.game.voting.append(player_id)
                        room.game.voted.append(member)
                        self.broadcast(
                            f"{member.nickname} voted for {room.game.players[player_id].member.nickname}", member
                        )

        elif message.startswith(client_commands.EXECUTE):
            if member.room_id:
                room = self.rooms[member.room_id]
                player = room.game.get_player(member)
                if room.game.active and room.game.daytime == "day":
                    player_id = int(message.split(" ")[1])
                    if player_id in room.game.players and member not in room.game.voted and player.alive:
                        room.game.voting.append(player_id)
                        room.game.voted.append(member)
                        self.broadcast(
                            f"{member.nickname} voted for {room.game.players[player_id].member.nickname}", member
                        )

        elif message.startswith(client_commands.SKIP):
            if member.room_id:
                room = self.rooms[member.room_id]
                player = room.game.get_player(member)
                if room.game.active and room.game.daytime == "day" and member not in room.game.voted and player.alive:
                    room.game.voting.append(0)
                    room.game.voted.append(member)
                    self.broadcast(f"{member.nickname} decided to skip", member)

        elif message.startswith(client_commands.VERIFY):
            if member.room_id:
                room = self.rooms[member.room_id]
                if room.game.active and room.game.daytime == "night" and room.game.active_role == "cherif" \
                        and room.game.active_role == room.game.get_player(member).role:
                    player_id = int(message.split(" ")[1])
                    if player_id in room.game.players and member not in room.game.voted:
                        player = room.game.players[player_id]
                        room.game.voted.append(member)
                        member.send(f"\n{player.member.nickname} is {player.role}\n")

        elif message.startswith(client_commands.SELF):
            if member.room_id:
                room = self.rooms[member.room_id]
                if room.game.active:
                    player = room.game.get_player(member)
                    member.send(f"{player.player_id}\t{player.member.nickname}\t{player.alive}")

        else:
            self.broadcast(f"{member.nickname}: " + message, member)

    def handle(self, member):
        while True:
            try:
                message = member.connection.recv(1024).decode("utf-8")
                ret = self.handle_text(member, message)
                if ret == 1:
                    self.exclude_member(member)
                    break
            except (ValueError, KeyError, IndexError):
                member.send("Something went wrong")
            except:
                self.exclude_member(member)
                break

    def broadcast(self, message, self_m=None):
        if self_m and self_m.room_id:
            room = self.rooms[self_m.room_id]
            if room.game.active and room.game.daytime == "night" and room.game.get_player(self_m).role == "mafia":
                for member in room.members:
                    if member != self_m and room.game.get_player(member).role == "mafia":
                        member.send(message)
            elif not room.game.active or (room.game.daytime == "day" and room.game.get_player(self_m).alive):
                for member in room.members:
                    if member != self_m:
                        member.send(message)
            elif room.game.active and not room.game.get_player(self_m).alive:
                for member in room.members:
                    if member != self_m and not room.game.get_player(member).alive:
                        member.send(message)

    def exclude_member(self, member):
        try:
            member.disconnect()
            print(f"{member.nickname} {member.address} left")
            if not member.room_id:
                return
            room = self.rooms[member.room_id]
            if room.game.active:
                room.game.exclude_player(member)
                room.game.set_default()
                self.broadcast("\nGAME WAS STOPPED\n")
            room.exclude_member(member)
            if room.members:
                room.set_admin(room.members[0])
            else:
                self.rooms.pop(room.room_id)
            self.broadcast(f"{member.nickname} left")
        except:
            pass


server = Server(HOST, PORT)
