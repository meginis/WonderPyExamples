import WonderPy.core.wwMain
from WonderPy.core.wwConstants import WWRobotConstants
from threading import Thread
import twitter
from queue import *
import eventlet
import socketio
'''
This example requires you to set up a Twitter Application (https://apps.twitter.com/) 
and provide your key and token below.

This example will listen for tweets to a specified account and parse the message looking for an action to perform.
Currently only drive and turn actions will be performed. Below are example tweets of valid actions assuming 
we are listening to the Twitter account @twitterBot:
@twitterBot drive forward 40
@twitterBot drive left 50
@twitterBot turn right 90
'''



class Direction(object):
    LEFT = 0
    RIGHT = 1
    FORWARD = 2
    BACK = 3


class ActionType(object):
    DRIVE = 0
    ROTATE = 1


DRIVE_ACTION_WORDS = ['GO', 'DRIVE', 'MOVE']
ROTATE_ACTION_WORDS = ['TURN', 'ROTATE', 'SPIN']
FORWARD_DIRECTION_WORDS = ['FORWARD']
BACK_DIRECTION_WORDS = ['BACK']
LEFT_DIRECTION_WORDS = ['LEFT']
RIGHT_DIRECTION_WORDS = ['RIGHT']

ROTATION_MAX = 180
ROTATION_MIN = -180
DRIVE_MAX = 100
DRIVE_MIN = -100

# populate these values with the values given by the Twitter API
# see https://python-twitter.readthedocs.io/en/latest/getting_started.html for instruction on how set up keys and tokens
TWITTER_CONSUMER_KEY = ""
TWITTER_CONSUMER_SECRET = ""
TWITTER_ACCESS_TOKEN_KEY = ""
TWITTER_ACCESS_TOKEN_SECRET = ""

# populate this list with the Twitter accounts you want to listen to
TWITTER_USERS = [""]
TWITTER_LANG = ["en"]


def is_numeric(s):
    '''
    Determines if a string is numeric (including negative and decimal numbers)
    :param s: string to check
    :return: Bool
    '''
    try:
        float(s)
        return True
    except ValueError:
        return False


class TwitterBot(object):
    def __init__(self):
        self._action_queue = Queue()
        self._twitter_api = None
        self._robot = None

    def on_connect(self, robot):
        '''
        Kick off async threads
        :param robot: The robot that was connected to
        :return: None
        '''

        if not robot.has_ability(WWRobotConstants.WWRobotAbilities.BODY_MOVE, True):
            # it doesn't do any harm to send drive commands to a robot with no wheels,
            # but it doesn't help either.
            print("%s cannot drive! try a different example." % (robot.name))
            return

        self._robot = robot
        print("starting async threads for %s" % (self._robot.name))
        self._async_thread1 = Thread(target=self.action_listener_async)
        self._async_thread1.start()
        self._async_thread3 = Thread(target=self.socketStartup)
        self._async_thread3.start()
        
    def socketStartup(self):
        sio = socketio.Server()
        app = socketio.WSGIApp(sio, static_files={
        '/': {'content_type': 'text/html', 'filename': './index.html'}
        })
        @sio.event
        def connect(sid, environ):
            print('connect ', sid)

        @sio.event
        def message(sid, data):
            self.parse_message(data)
            print('message ', data)

        @sio.event
        def disconnect(sid):
            print('disconnect ', sid)
        print('Starting up server')
        eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
    def action_listener_async(self):
        '''
        Performs actions placed on the action queue
        :return: None
        '''
        print("listening")
        while True:
            action = self._action_queue.get(block=True)

            print("Performing action: " + action["readable"])

            if action["type"] == ActionType.DRIVE:
                self.perform_drive(action["direction"], action["value"])
            elif action["type"] == ActionType.ROTATE:
                self.perform_rotate(action["direction"], action["value"])

    def parse_message(self, message):
        '''
        Parses a message and turns it into actions and adds them to the action queue
        Each action must follow the order <action type> <direction> <value>
        :param message: The message to parse
        :param tweet_id: The id of the tweet that send this message. Used to send response tweets
        :return: None
        '''
        message = message.upper()
        action = None
        direction = None
        value = None
        readable_action = ""

        for word in message.split():
            if action == None:
                if word in DRIVE_ACTION_WORDS:
                    action = ActionType.DRIVE
                    readable_action += word.lower() + " "
                elif word in ROTATE_ACTION_WORDS:
                    action = ActionType.ROTATE
                    readable_action += word.lower() + " "
            elif direction == None:
                if word in BACK_DIRECTION_WORDS:
                    direction = Direction.BACK
                    readable_action += word.lower() + " "
                elif word in FORWARD_DIRECTION_WORDS:
                    direction = Direction.FORWARD
                    readable_action += word.lower() + " "
                elif word in LEFT_DIRECTION_WORDS:
                    direction = Direction.LEFT
                    readable_action += word.lower() + " "
                elif word in RIGHT_DIRECTION_WORDS:
                    direction = Direction.RIGHT
                    readable_action += word.lower() + " "
            elif value == None and is_numeric(word):
                value = float(word)
                readable_action += word + " "

            # We have found an action, direction, and value
            if action != None and direction != None and value != None:
                if self.are_params_valid(action, direction, value):
                    print("Added: {0}, {1}, {2}".format(action, direction, value))
                else:
                    # Command given is not valid
                    # Send a reply informing the user
                    print("Invalid command: {0}".format(readable_action))
                return
    
    def are_params_valid(self, action, direction, value):
        '''
        Validates the action parameters to make sure it is a valid action
        :param action: The type of action
        :param direction: The direction of the action
        :param value: The value associated with the action
        :return: True if valid, False if not
        '''
        if action != None and direction != None and value != None:
            if action == ActionType.DRIVE:
                return value >= DRIVE_MIN and value <= DRIVE_MAX
            if action == ActionType.ROTATE:
                return (direction == Direction.LEFT or direction == Direction.RIGHT) and\
                       value >= ROTATION_MIN and value <= ROTATION_MAX
        return False

    def perform_drive(self, direction, distance):
        '''
        Performs a drive action
        :param direction: Direction to drive
        :param distance: Distance to drive
        :return: None
        '''

        if direction == Direction.FORWARD:
            self._robot.commands.body.do_forward(distance, abs(distance))
        elif direction == Direction.BACK:
            self._robot.commands.body.do_forward(-distance, abs(distance))
        elif direction == Direction.LEFT:
            # rotate left and drive forward
            self.perform_rotate(Direction.LEFT, 90)
            self._robot.commands.body.do_forward(distance, abs(distance))
        elif direction == Direction.RIGHT:
            # rotate right and drive forward
            self.perform_rotate(Direction.RIGHT, 90)
            self._robot.cmds.body.do_forward(distance, abs(distance))

    def perform_rotate(self, direction, degs):
        '''
        Performs a rotation action
        :param direction: direction to rotate
        :param degs: degrees to rotate
        :return: None
        '''
        if direction == Direction.LEFT:
            self._robot.commands.body.do_turn(degs, abs(degs))
        elif direction == Direction.RIGHT:
            self._robot.commands.body.do_turn(-degs, abs(degs))


if __name__ == "__main__":
    WonderPy.core.wwMain.start(TwitterBot())
