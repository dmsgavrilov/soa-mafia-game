class ClientCommands:
    LEAVE = "/leave"
    MEMBERS = "/members"
    CREATE_ROOM = "/create_room"
    CONNECT = "/connect"
    SET_SIZE = "/set_size"
    START_GAME = "/start_game"
    ROOMS = "/rooms"
    VERIFY = "/verify"  # For cherif
    KILL = "/kill"  # For cherif and mafia
    EXECUTE = "/execute"  # For citizen
    SKIP = "/skip"  # For citizen
    PLAYERS = "/players"
    SELF = "/me"
    HELP = "/help"


client_commands = ClientCommands()
