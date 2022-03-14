class ServerCommands:
    NICKNAME = "NICK"


class ClientCommands:
    LEAVE = "/leave"
    MEMBERS = "/members"
    CREATE_ROOM = "/create_room"
    CONNECT = "/connect"
    SET_SIZE = "/set_size"
    START_GAME = "/start_game"


server_commands = ServerCommands()
client_commands = ClientCommands()
