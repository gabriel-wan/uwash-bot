from enum import Enum

USER_DATA_KEY_HOUSE = "house"
USER_DATA_KEY_CALLBACK = "callback"
USER_DATA_KEY_BOT_MSG = "bot_msg"

COLLEGE_HOUSES = {
    "capt": ["ROC", "Dragon", "Garuda", "Phoenix", "Tulpar"],
    "acacia": ["Aeon", "Nous", "Zenith"],
    "tembusu": ["Shan", "Ora", "Gaja", "Tancho", "Ponya"],
    "rc4": ["Acquila", "Noctua", "Ursa", "Leo", "Draco"],
    "rvrc": ["Aonyx", "Chelonia", "Manis", "Orcaella", "Panthera", "Rusa", "Strix"],
    "nusc": ["Kairos", "Levios", "Idalia", "Osceanna", "Corvex", "Perseus"],
}

HOUSES = {
    "ROC": "\U0001F499\U0001F43A ROC \U0001F43A\U0001F499",
    "Dragon": "\U0001F340\U0001F409 Dragon \U0001F409\U0001F340",
    "Garuda": "\U0001F34C\U0001F648 Garuda \U0001F648\U0001F34C",
    "Phoenix": "\U0001F525\U0001F425 Phoenix \U0001F425\U0001F525",
    "Tulpar": "\U0001F5A4\U0001F434 Tulpar \U0001F434\U0001F5A4",
    "Aeon": "Aeon",
    "Nous": "Nous",
    "Zenith": "Zenith",
    "Shan": "Shan",
    "Ora": "Ora",
    "Gaja": "Gaja",
    "Tancho": "Tancho",
    "Ponya": "Ponya",
    "Acquila": "Acquila",
    "Noctua": "Noctua",
    "Ursa": "Ursa",
    "Leo": "Leo",
    "Draco": "Draco",
    "Aonyx": "Aonyx",
    "Chelonia": "Chelonia",
    "Manis": "Manis",
    "Orcaella": "Orcaella",
    "Panthera": "Panthera",
    "Rusa": "Rusa",
    "Strix": "Strix",
    "Kairos": "Kairos",
    "Levios": "Levios",
    "Idalia": "Idalia",
    "Osceanna": "Osceanna",
    "Corvex": "Corvex",
    "Perseus": "Perseus",
}

HOUSE_TO_COLLEGE = {
    house: college
    for college, houses in COLLEGE_HOUSES.items()
    for house in houses
}

HOUSE_ALIASES = {
    "house-1": "Kairos",
    "house-2": "Levios",
    "house-3": "Idalia",
    "house-4": "Osceanna",
}
MACHINE_NAMES = ["Dryer One", "Dryer Two", "Dryer Three", "Washer One", "Washer Two", "Washer Three"]


class ConvState(str, Enum):
    RequestConfirmSelect = "RequestConfirmSelect"
    ConfirmSelect = "ConfirmSelect"
    SelectHouse = "SelectHouse"
    StatusSelectHouse = "StatusSelectHouse"
    SelectDuration = "SetDuration"


SELECT_COMMAND_DESCRIPTION = "Select the washer/dryer that you want to use"
STATUS_COMMAND_DESCRIPTION = "Check the status of Washers and Dryers"

WELCOME_MESSAGE = f"Welcome to CAPT Laundry Bot!\n\nUse the following commands to use this bot:\n/select: {SELECT_COMMAND_DESCRIPTION}\n/status: {STATUS_COMMAND_DESCRIPTION}\n\nThank you for using the bot!\nDeveloped by: @jloh02, @zozibo"
