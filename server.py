import socket
import threading
from random import shuffle

from commands import server_commands, client_commands

HOST = '127.0.0.1'
PORT = 5000


class Member:
    def __init__(self, connection, address, nickname):
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
    def __init__(self, member, role):
        self._member = member
        self._role = role  # Citizen, Cherif, Mafia
        self._is_alive = True

    @property
    def member(self):
        return self._member

    @property
    def role(self):
        return self._role

    @property
    def is_alive(self):
        return self._is_alive


class Game:
    def __init__(self):
        self.players = {}
        self.active = False

    def start(self, room):
        if room.size >= min(len(room.members), 4):
            self.players = self._distribute(room.members)
            self.active = True
            return 1
        return 0

    def _distribute(self, room_members):
        distribution = []
        mafias_count = 1 + int((len(room_members) - 4) / 2)
        for i in range(mafias_count):
            distribution.append("Mafia")
        distribution.append("Cherif")
        citizens_count = len(room_members) - mafias_count - 1
        for i in range(citizens_count):
            distribution.append("Citizen")
        shuffle(distribution)
        return [Player(room_members[i], distribution[i]) for i in range(len(distribution))]


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

    def start_game(self):
        return self._game.start(self)

    def is_admin(self, member):
        return self._admin == member

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
        rooms_txt = "|\tID\t|\tTITLE\t|\tMEMBERS\t|\n"
        for _, room in self.rooms.items():
            if not room.game.active:
                rooms_txt += f"|\t{room.room_id}\t|\t{room.title}\t|\t{len(room.members)} / {room.size}\t|"
        return rooms_txt

    def serialize_members(self, room):
        # TODO
        pass

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
                   "/connect {room_id} - to connect to room\n")
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
            if member.room_id:
                room = self.rooms[member.room_id]
                room.remove_member(member)
                member.disconnect()

        elif message.startswith(client_commands.CONNECT):
            room_to_connect = int(message.split(" ")[1])
            room = self.rooms.get(room_to_connect, None)
            if room:
                if len(room.members) + 1 <= room.size:
                    room.add_member(member)
                    member.set_room(room_to_connect)
                    member.send("You joined the room")
                    self.broadcast(f"{member.nickname} joined!", member)
                else:
                    member.send("Can't connect, room is full")
            else:
                member.send("Room doesn't exist or room_id is not valid")

        elif message.startswith(client_commands.MEMBERS):
            if member.room_id:
                member.send(self.serialize_members(self.rooms[member.room_id]))
            else:
                member.send("You are not in room")

        elif message.startswith(client_commands.SET_SIZE):
            if member.room_id:
                size = int(message.split(" ")[1])
                room = self.rooms[member.room_id]
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
                if room.is_admin(member):
                    ret = room.start_game()
                    if not ret:
                        member.send("")
                else:
                    member.send("You don't have enough permissions")
            else:
                member.send("You are not in room")

        else:
            self.broadcast(message, member)

    def handle(self, member):
        while True:
            message = member.connection.recv(1024).decode("utf-8")
            self.handle_text(member, message)

    def broadcast(self, message, self_m=None):
        if self_m.room_id:
            room = self.rooms[self_m.room_id]
            for member in room.members:
                if member != self_m:
                    member.send(message)


server = Server(HOST, PORT)
