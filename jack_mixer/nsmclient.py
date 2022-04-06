#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyNSMClient -  A New Session Manager Client-Library in one file.

The Non-Session-Manager by Jonathan Moore Liles <male@tuxfamily.org>: http://non.tuxfamily.org/nsm/
New Session Manager by Nils Hilbricht et al  https://new-session-manager.jackaudio.org
With help from code fragments from https://github.com/attwad/python-osc ( DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE v2 )

MIT License

Copyright (c) since 2014: Laborejo Software Suite <info@laborejo.org>, All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import logging;
logger: logging.Logger  #filled by init with client logger.

import struct
import socket
from os import getenv, getpid, kill
import os
import os.path
import shutil
from uuid import uuid4
from sys import argv
from signal import signal, SIGTERM, SIGINT, SIGKILL #react to exit signals to close the client gracefully. Or kill if the client fails to do so.
from urllib.parse import urlparse

class _IncomingMessage(object):
    """Representation of a parsed datagram representing an OSC message.

    An OSC message consists of an OSC Address Pattern followed by an OSC
    Type Tag String followed by zero or more OSC Arguments.
    """

    def __init__(self, dgram):
        #NSM Broadcasts are bundles, but very simple ones. We only need to care about the single message it contains.
        #Therefore we can strip the bundle prefix and handle it as normal message.
        if b"#bundle" in dgram:
            bundlePrefix, singleMessage = dgram.split(b"/", maxsplit=1)
            dgram = b"/" + singleMessage  # / eaten by split
            self.isBroadcast = True
        else:
            self.isBroadcast = False
        self.LENGTH = 4 #32 bit
        self._dgram = dgram
        self._parameters = []
        self.parse_datagram()


    def get_int(self, dgram, start_index):
        """Get a 32-bit big-endian two's complement integer from the datagram.

        Args:
        dgram: A datagram packet.
        start_index: An index where the integer starts in the datagram.

        Returns:
        A tuple containing the integer and the new end index.

        Raises:
        ValueError if the datagram could not be parsed.
        """
        try:
            if len(dgram[start_index:]) < self.LENGTH:
                raise ValueError('Datagram is too short')
            return (
                struct.unpack('>i', dgram[start_index:start_index + self.LENGTH])[0], start_index + self.LENGTH)
        except (struct.error, TypeError) as e:
            raise ValueError('Could not parse datagram %s' % e)

    def get_string(self, dgram, start_index):
        """Get a python string from the datagram, starting at pos start_index.

        We receive always the full string, but handle only the part from the start_index internally.
        In the end return the offset so it can be added to the index for the next parameter.
        Each subsequent call handles less of the same string, starting further to the right.

        According to the specifications, a string is:
        "A sequence of non-null ASCII characters followed by a null,
        followed by 0-3 additional null characters to make the total number
        of bits a multiple of 32".

        Args:
        dgram: A datagram packet.
        start_index: An index where the string starts in the datagram.

        Returns:
        A tuple containing the string and the new end index.

        Raises:
        ValueError if the datagram could not be parsed.
        """
        #First test for empty string, which is nothing, followed by a terminating \x00 padded by three additional \x00.
        if dgram[start_index:].startswith(b"\x00\x00\x00\x00"):
            return "", start_index + 4

        #Otherwise we have a non-empty string that must follow the rules of the docstring.

        offset = 0
        try:
            while dgram[start_index + offset] != 0:
                offset += 1
            if offset == 0:
                raise ValueError('OSC string cannot begin with a null byte: %s' % dgram[start_index:])
            # Align to a byte word.
            if (offset) % self.LENGTH == 0:
                offset += self.LENGTH
            else:
                offset += (-offset % self.LENGTH)
            # Python slices do not raise an IndexError past the last index,
                # do it ourselves.
            if offset > len(dgram[start_index:]):
                raise ValueError('Datagram is too short')
            data_str = dgram[start_index:start_index + offset]
            return data_str.replace(b'\x00', b'').decode('utf-8'), start_index + offset
        except IndexError as ie:
            raise ValueError('Could not parse datagram %s' % ie)
        except TypeError as te:
            raise ValueError('Could not parse datagram %s' % te)

    def get_float(self, dgram, start_index):
        """Get a 32-bit big-endian IEEE 754 floating point number from the datagram.

          Args:
            dgram: A datagram packet.
            start_index: An index where the float starts in the datagram.

          Returns:
            A tuple containing the float and the new end index.

          Raises:
            ValueError if the datagram could not be parsed.
        """
        try:
            return (struct.unpack('>f', dgram[start_index:start_index + self.LENGTH])[0], start_index + self.LENGTH)
        except (struct.error, TypeError) as e:
            raise ValueError('Could not parse datagram %s' % e)

    def parse_datagram(self):
        try:
            self._address_regexp, index = self.get_string(self._dgram, 0)
            if not self._dgram[index:]:
                # No params is legit, just return now.
                return

            # Get the parameters types.
            type_tag, index = self.get_string(self._dgram, index)
            if type_tag.startswith(','):
                type_tag = type_tag[1:]

            # Parse each parameter given its type.
            for param in type_tag:
                if param == "i":  # Integer.
                    val, index = self.get_int(self._dgram, index)
                elif param == "f":  # Float.
                    val, index = self.get_float(self._dgram, index)
                elif param == "s":  # String.
                    val, index = self.get_string(self._dgram, index)
                else:
                    logger.warning("Unhandled parameter type: {0}".format(param))
                    continue
                self._parameters.append(val)
        except ValueError as pe:
            #raise ValueError('Found incorrect datagram, ignoring it', pe)
            # Raising an error is not ignoring it!
            logger.warning("Found incorrect datagram, ignoring it. {}".format(pe))

    @property
    def oscpath(self):
        """Returns the OSC address regular expression."""
        return self._address_regexp

    @staticmethod
    def dgram_is_message(dgram):
        """Returns whether this datagram starts as an OSC message."""
        return dgram.startswith(b'/')

    @property
    def size(self):
        """Returns the length of the datagram for this message."""
        return len(self._dgram)

    @property
    def dgram(self):
        """Returns the datagram from which this message was built."""
        return self._dgram

    @property
    def params(self):
        """Convenience method for list(self) to get the list of parameters."""
        return list(self)

    def __iter__(self):
        """Returns an iterator over the parameters of this message."""
        return iter(self._parameters)

class _OutgoingMessage(object):
    def __init__(self, oscpath):
        self.LENGTH = 4 #32 bit
        self.oscpath = oscpath
        self._args = []

    def write_string(self, val):
        dgram = val.encode('utf-8')
        diff = self.LENGTH - (len(dgram) % self.LENGTH)
        dgram += (b'\x00' * diff)
        return dgram

    def write_int(self, val):
        return struct.pack('>i', val)

    def write_float(self, val):
        return struct.pack('>f', val)

    def add_arg(self, argument):
        t = {str:"s", int:"i", float:"f"}[type(argument)]
        self._args.append((t, argument))

    def build(self):
        dgram = b''

        #OSC Path
        dgram += self.write_string(self.oscpath)

        if not self._args:
            dgram += self.write_string(',')
            return dgram

        # Write the parameters.
        arg_types = "".join([arg[0] for arg in self._args])
        dgram += self.write_string(',' + arg_types)
        for arg_type, value in self._args:
            f = {"s":self.write_string, "i":self.write_int, "f":self.write_float}[arg_type]
            dgram += f(value)
        return dgram

class NSMNotRunningError(Exception):
    """Error raised when environment variable $NSM_URL was not found."""

class NSMClient(object):
    """The representation of the host programs as NSM sees it.
    Technically consists of an udp server and a udp client.

    Does not run an event loop itself and depends on the host loop.
    E.g. a Qt timer or just a simple while True: sleep(0.1) in Python."""
    def __init__(self, prettyName, supportsSaveStatus, saveCallback, openOrNewCallback, exitProgramCallback, hideGUICallback=None, showGUICallback=None, broadcastCallback=None, sessionIsLoadedCallback=None, loggingLevel = "info"):

        self.nsmOSCUrl = self.getNsmOSCUrl() #this fails and raises NSMNotRunningError if NSM is not available. Host programs can ignore it or exit their program.

        self.realClient = True
        self.cachedSaveStatus = None #save status checks for this.

        global logger
        logger = logging.getLogger(prettyName)
        logger.info("import")
        if loggingLevel == "info" or loggingLevel == 20:
            logging.basicConfig(level=logging.INFO) #development
            logger.info("Starting PyNSM2 Client with logging level INFO. Switch to 'error' for a release!") #the NSM name is not ready yet so we just use the pretty name
        elif loggingLevel == "error" or loggingLevel == 40:
            logging.basicConfig(level=logging.ERROR) #production
        else:
            logging.warning("Unknown logging level: {}. Choose 'info' or 'error'".format(loggingLevel))
            logging.basicConfig(level=logging.INFO) #development

        #given parameters,
        self.prettyName = prettyName #keep this consistent! Settle for one name.
        self.supportsSaveStatus = supportsSaveStatus
        self.saveCallback = saveCallback
        self.exitProgramCallback = exitProgramCallback
        self.openOrNewCallback = openOrNewCallback #The host needs to: Create a jack client with ourClientNameUnderNSM - Open the saved file and all its resources
        self.broadcastCallback = broadcastCallback
        self.hideGUICallback = hideGUICallback
        self.showGUICallback = showGUICallback
        self.sessionIsLoadedCallback = sessionIsLoadedCallback

        #Reactions get the raw _IncomingMessage OSC object
        #A client can add to reactions.
        self.reactions = {
                          "/nsm/client/save" : self._saveCallback,
                          "/nsm/client/show_optional_gui" : lambda msg: self.showGUICallback(),
                          "/nsm/client/hide_optional_gui" : lambda msg: self.hideGUICallback(),
                          "/nsm/client/session_is_loaded" : self._sessionIsLoadedCallback,
                          #Hello source-code reader. You can add your own reactions here by nsmClient.reactions[oscpath]=func, where func gets the raw _IncomingMessage OSC object as argument.
                          #broadcast is handled directly by the function because it has more parameters
                          }
        #self.discardReactions = set(["/nsm/client/session_is_loaded"])
        self.discardReactions = set()

        #Networking and Init
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #internet, udp
        self.sock.bind(('', 0)) #pick a free port on localhost.
        ip, port = self.sock.getsockname()
        self.ourOscUrl = f"osc.udp://{ip}:{port}/"

        self.executableName = self.getExecutableName()

        #UNIX Signals. Used for quit.
        signal(SIGTERM, self.sigtermHandler) #NSM sends only SIGTERM. #TODO: really? pynsm version 1 handled sigkill as well.
        signal(SIGINT, self.sigtermHandler)

        #The following instance parameters are all set in announceOurselves
        self.serverFeatures = None
        self.sessionName = None
        self.ourPath = None
        self.ourClientNameUnderNSM = None
        self.ourClientId = None # the "file extension" of ourClientNameUnderNSM
        self.isVisible = None #set in announceGuiVisibility
        self.saveStatus = True # true is clean. false means we need saving.

        self.announceOurselves()

        assert self.serverFeatures, self.serverFeatures
        assert self.sessionName, self.sessionName
        assert self.ourPath, self.ourPath
        assert self.ourClientNameUnderNSM, self.ourClientNameUnderNSM

        self.sock.setblocking(False) #We have waited for tha handshake. Now switch blocking off because we expect sock.recvfrom to be empty in 99.99...% of the time so we shouldn't wait for the answer.
        #After this point the host must include self.reactToMessage in its event loop

        #We assume we are save at startup.
        self.announceSaveStatus(isClean = True)

        logger.info("NSMClient client init complete. Going into listening mode.")


    def reactToMessage(self):
        """This is the main loop message. It is added to the clients event loop."""
        try:
            data, addr = self.sock.recvfrom(4096) #4096 is quite big. We don't expect nsm messages this big. Better safe than sorry. However, messages will crash the program if they are bigger than 4096.
        except BlockingIOError: #happens while no data is received. Has nothing to do with blocking or not.
            return None

        msg = _IncomingMessage(data)
        if msg.oscpath in self.reactions:
            self.reactions[msg.oscpath](msg)
        elif msg.oscpath in self.discardReactions:
            pass
        elif msg.oscpath == "/reply" and msg.params == ["/nsm/server/open", "Loaded."]: #NSM sends that all programs of the session were loaded.
            logger.info ("Got /reply Loaded from NSM Server")
        elif msg.oscpath == "/reply" and msg.params == ["/nsm/server/save", "Saved."]: #NSM sends that all program-states are saved. Does only happen from the general save instruction, not when saving our client individually
            logger.info ("Got /reply Saved from NSM Server")
        elif msg.isBroadcast:
            if self.broadcastCallback:
                logger.info (f"Got broadcast with messagePath {msg.oscpath} and listOfArguments {msg.params}")
                self.broadcastCallback(self.ourPath, self.sessionName, self.ourClientNameUnderNSM, msg.oscpath, msg.params)
            else:
                logger.info (f"No callback for broadcast! Got messagePath {msg.oscpath} and listOfArguments {msg.params}")
        elif msg.oscpath == "/error":
            logger.warning("Got /error from NSM Server. Path: {} , Parameter: {}".format(msg.oscpath, msg.params))
        else:
            logger.warning("Reaction not implemented:. Path: {} , Parameter: {}".format(msg.oscpath, msg.params))


    def send(self, path:str, listOfParameters:list, host=None, port=None):
        """Send any osc message. Defaults to nsmd URL.
        Will not wait for an answer but return None."""
        if host and port:
            url = (host, port)
        else:
            url = self.nsmOSCUrl
        msg = _OutgoingMessage(path)
        for arg in listOfParameters:
            msg.add_arg(arg) #type is auto-determined by outgoing message
        self.sock.sendto(msg.build(), url)

    def getNsmOSCUrl(self):
        """Return and save the nsm osc url or raise an error"""
        nsmOSCUrl = getenv("NSM_URL")
        if not nsmOSCUrl:
            raise NSMNotRunningError("New-Session-Manager environment variable $NSM_URL not found.")
        else:
            #osc.udp://hostname:portnumber/
            o = urlparse(nsmOSCUrl)
            #return o.hostname, o.port #this always make the hostname lowercase. usually it does not matter, but we got crash reports. Alternative:
            return o.netloc.split(":")[0], o.port

    def getExecutableName(self):
        """Finding the actual executable name can be a bit hard
        in Python. NSM wants the real starting point, even if
        it was a bash script.
        """
        #TODO: I really don't know how to find out the name of the bash script
        fullPath = argv[0]
        assert os.path.dirname(fullPath) in os.environ["PATH"], (fullPath, os.path.dirname(fullPath), os.environ["PATH"]) #NSM requires the executable to be in the path. No excuses. This will never happen since the reference NSM server-GUI already checks for this.

        executableName = os.path.basename(fullPath)
        assert not "/" in executableName, executableName #see above.
        return executableName

    def announceOurselves(self):
        """Say hello to NSM and tell it we are ready to receive
        instructions

        /nsm/server/announce s:application_name s:capabilities s:executable_name i:api_version_major i:api_version_minor i:pid"""

        def buildClientFeaturesString():
            #:dirty:switch:progress:
            result = []
            if self.supportsSaveStatus:
                result.append("dirty")
            if self.hideGUICallback and self.showGUICallback:
                result.append("optional-gui")
            if result:
                return ":".join([""] + result + [""])
            else:
                return ""

        logger.info("Sending our NSM-announce message")

        announce = _OutgoingMessage("/nsm/server/announce")
        announce.add_arg(self.prettyName)  #s:application_name
        announce.add_arg(buildClientFeaturesString()) #s:capabilities
        announce.add_arg(self.executableName)  #s:executable_name
        announce.add_arg(1)  #i:api_version_major
        announce.add_arg(2)  #i:api_version_minor
        announce.add_arg(int(getpid())) #i:pid
        hostname, port = self.nsmOSCUrl
        assert hostname, self.nsmOSCUrl
        assert port, self.nsmOSCUrl
        self.sock.sendto(announce.build(), self.nsmOSCUrl)

        #Wait for /reply (aka 'Howdy, what took you so long?)
        data, addr = self.sock.recvfrom(1024)
        msg = _IncomingMessage(data)

        if msg.oscpath == "/error":
            originalMessage, errorCode, reason = msg.params
            logger.error("Code {}: {}".format(errorCode, reason))
            quit()

        elif msg.oscpath == "/reply":
            nsmAnnouncePath, welcomeMessage, managerName, self.serverFeatures = msg.params
            assert nsmAnnouncePath == "/nsm/server/announce", nsmAnnouncePath
            logger.info("Got /reply " + welcomeMessage)

            #Wait for /nsm/client/open
            data, addr = self.sock.recvfrom(1024)
            msg = _IncomingMessage(data)
            assert msg.oscpath == "/nsm/client/open", msg.oscpath
            self.ourPath, self.sessionName, self.ourClientNameUnderNSM = msg.params
            self.ourClientId = os.path.splitext(self.ourClientNameUnderNSM)[1][1:]
            logger.info("Got '/nsm/client/open' from NSM. Telling our client to load or create a file with name {}".format(self.ourPath))
            self.openOrNewCallback(self.ourPath, self.sessionName, self.ourClientNameUnderNSM) #Host function to either load an existing session or create a new one.
            logger.info("Our client should be done loading or creating the file {}".format(self.ourPath))
            replyToOpen = _OutgoingMessage("/reply")
            replyToOpen.add_arg("/nsm/client/open")
            replyToOpen.add_arg("{} is opened or created".format(self.prettyName))
            self.sock.sendto(replyToOpen.build(), self.nsmOSCUrl)
        else:
            raise ValueError("Unexpected message path after announce: {}".format((msg.oscpath, msg.params)))

    def announceGuiVisibility(self, isVisible):
        message = "/nsm/client/gui_is_shown" if isVisible else "/nsm/client/gui_is_hidden"
        self.isVisible = isVisible
        guiVisibility = _OutgoingMessage(message)
        logger.info("Telling NSM that our clients switched GUI visibility to: {}".format(message))
        self.sock.sendto(guiVisibility.build(), self.nsmOSCUrl)

    def announceSaveStatus(self, isClean):
        """Only send to the NSM Server if there was really a change"""
        if not self.supportsSaveStatus:
            return

        if not isClean == self.cachedSaveStatus:
            message = "/nsm/client/is_clean" if isClean else "/nsm/client/is_dirty"
            self.cachedSaveStatus = isClean
            saveStatus = _OutgoingMessage(message)
            logger.info("Telling NSM that our clients save state is now: {}".format(message))
            self.sock.sendto(saveStatus.build(), self.nsmOSCUrl)

    def _saveCallback(self, msg):
        logger.info("Telling our client to save as {}".format(self.ourPath))
        self.saveCallback(self.ourPath, self.sessionName, self.ourClientNameUnderNSM)
        replyToSave = _OutgoingMessage("/reply")
        replyToSave.add_arg("/nsm/client/save")
        replyToSave.add_arg("{} saved".format(self.prettyName))
        self.sock.sendto(replyToSave.build(), self.nsmOSCUrl)
        #it is assumed that after saving the state is clear
        self.announceSaveStatus(isClean = True)


    def _sessionIsLoadedCallback(self, msg):
        if self.sessionIsLoadedCallback:
            logger.info("Received 'Session is Loaded'. Our client supports it. Forwarding message...")
            self.sessionIsLoadedCallback()
        else:
            logger.info("Received 'Session is Loaded'. Our client does not support it, which is the default. Discarding message...")

    def sigtermHandler(self, signal, frame):
        """Wait for the user to quit the program

        The user function does not need to exit itself.
        Just shutdown audio engines etc.

        It is possible, that the client does not implement quit
        properly. In that case NSM protocol demands that we quit anyway.
        No excuses.

        Achtung GDB! If you run your program with
            gdb --args python foo.py
        the Python signal handler will not work. This has nothing to do with this library.
        """
        logger.info("Telling our client to quit.")
        self.exitProgramCallback(self.ourPath, self.sessionName, self.ourClientNameUnderNSM)
        #There is a chance that exitProgramCallback will hang and the program won't quit. However, this is broken design and bad programming. We COULD place a timeout here and just kill after 10s or so, but that would make quitting our responsibility and fixing a broken thing.
        #If we reach this point we have reached the point of no return. Say goodbye.
        logger.warning("Client did not quit on its own. Sending SIGKILL.")
        kill(getpid(), SIGKILL)
        logger.error("SIGKILL did nothing. Do it manually.")

    def debugResetDataAndExit(self):
        """This is solely meant for debugging and testing. The user way of action should be to
        remove the client from the session and add a new instance, which will get a different
        NSM-ID.
        Afterwards we perform a clean exit."""
        logger.warning("debugResetDataAndExit will now delete {} and then request an exit.".format(self.ourPath))
        if os.path.exists(self.ourPath):
            if os.path.isfile(self.ourPath):
                try:
                    os.remove(self.ourPath)
                except Exception as e:
                    logger.info(e)
            elif os.path.isdir(self.ourPath):
                try:
                    shutil.rmtree(self.ourPath)
                except Exception as e:
                    logger.info(e)
        else:
            logger.info("{} does not exist.".format(self.ourPath))
        self.serverSendExitToSelf()

    def serverSendExitToSelf(self):
        """If you want a very strict client you can block any non-NSM quit-attempts, like ignoring a
        qt closeEvent, and instead send the NSM Server a request to close this client.
        This method is a shortcut to do just that.
        """
        logger.info("Sending SIGTERM to ourselves to trigger the exit callback.")
        #if "server-control" in self.serverFeatures:
        #    message = _OutgoingMessage("/nsm/server/stop")
        #    message.add_arg("{}".format(self.ourClientId))
        #    self.sock.sendto(message.build(), self.nsmOSCUrl)
        #else:
        kill(getpid(), SIGTERM) #this calls the exit callback

    def serverSendSaveToSelf(self):
        """Some clients want to offer a manual Save function, mostly for psychological reasons.
        We offer a clean solution in calling this function which will trigger a round trip over the
        NSM server so our client thinks it received a Save instruction. This leads to a clean
        state with a good saveStatus and no required extra functionality in the client."""

        logger.info("instructing the NSM-Server to send Save to ourselves.")
        if "server-control" in self.serverFeatures:
            #message = _OutgoingMessage("/nsm/server/save") # "Save All" Command.
            message = _OutgoingMessage("/nsm/gui/client/save")
            message.add_arg("{}".format(self.ourClientId))
            self.sock.sendto(message.build(), self.nsmOSCUrl)
        else:
            logger.warning("...but the NSM-Server does not support server control. Server only supports: {}".format(self.serverFeatures))

    def changeLabel(self, label:str):
        """This function is implemented because it is provided by NSM. However, it does not much.
        The message gets received but is not saved.
        The official NSM GUI uses it but then does not save it.
        We would have to send it every startup ourselves.

        This is fine for us as clients, but you need to provide a GUI field to enter that label."""
        logger.info("Telling the NSM-Server that our label is now " + label)
        message = _OutgoingMessage("/nsm/client/label")
        message.add_arg(label)  #s:label
        self.sock.sendto(message.build(), self.nsmOSCUrl)

    def broadcast(self, path:str, arguments:list):
        """/nsm/server/broadcast s:path [arguments...]
        We, as sender, will not receive the broadcast back.

        Broadcasts starting with /nsm are not allowed and will get discarded by the server
        """
        if path.startswith("/nsm"):
            logger.warning("Attempted broadbast starting with /nsm. Not allwoed")
        else:
            logger.info("Sending broadcast " + path + repr(arguments))
            message = _OutgoingMessage("/nsm/server/broadcast")
            message.add_arg(path)
            for arg in arguments:
                message.add_arg(arg)  #type autodetect
            self.sock.sendto(message.build(), self.nsmOSCUrl)

    def importResource(self, filePath):
        """aka. import into session

        ATTENTION! You will still receive an absolute path from this function. You need to make
        sure yourself that this path will not be saved in your save file, but rather use a place-
        holder that gets replaced by the actual session path each time. A good point is after
        serialisation. search&replace for the session prefix ("ourPath") and replace it with a tag
        e.g. <sessionDirectory>. The opposite during load.
        Only such a behaviour will make your session portable.

        Do not use the following pattern: An alternative that comes to mind is to only work with
        relative paths and force your programs workdir to the session directory. Better work with
        absolute paths internally .

        Symlinks given path into session dir and returns the linked path relative to the ourPath.
        It can handles single files as well as whole directories.

        if filePath is already a symlink we do not follow it. os.path.realpath or os.readlink will
        not be used.

        Multilayer links may indicate a users ordering system that depends on
        abstractions. e.g. with mounted drives under different names which get symlinked to a
        reliable path.

        Basically do not question the type of our input filePath.

        tar with the follow symlink option has os.path.realpath behaviour and therefore is able
        to follow multiple levels of links anyway.

        A hardlink does not count as a link and will be detected and treated as real file.

        Cleaning up a session directory is either responsibility of the user
        or of our client program. We do not provide any means to unlink or delete files from the
        session directory.
        """

        #Even if the project was not saved yet now it is time to make our directory in the NSM dir.
        if not os.path.exists(self.ourPath):
            os.makedirs(self.ourPath)

        filePath = os.path.abspath(filePath) #includes normalisation
        if not os.path.exists(self.ourPath):raise FileNotFoundError(self.ourPath)
        if not os.path.isdir(self.ourPath): raise NotADirectoryError(self.ourPath)
        if not os.access(self.ourPath, os.W_OK): raise PermissionError("not writable", self.ourPath)

        if not os.path.exists(filePath):raise FileNotFoundError(filePath)
        if os.path.isdir(filePath): raise IsADirectoryError(filePath)
        if not os.access(filePath, os.R_OK): raise PermissionError("not readable", filePath)

        filePathInOurSession = os.path.commonprefix([filePath, self.ourPath]) == self.ourPath
        linkedPath = os.path.join(self.ourPath, os.path.basename(filePath))
        linkedPathAlreadyExists = os.path.exists(linkedPath)

        if not os.access(os.path.dirname(linkedPath), os.W_OK): raise PermissionError("not writable", os.path.dirname(linkedPath))


        if filePathInOurSession:
            #loadResource from our session dir. Portable session, manually copied beforehand or just loading a link again.
            linkedPath = filePath #we could return here, but we continue to get the tests below.
            logger.info(f"tried to import external resource {filePath} but this is already in our session directory. We use this file directly instead. ")

        elif linkedPathAlreadyExists and os.readlink(linkedPath) == filePath:
            #the imported file already exists as link in our session dir. We do not link it again but simply report the existing link.
            #We only check for the first target of the existing link and do not follow it through to a real file.
            #This way all user abstractions and file structures will be honored.
            linkedPath = linkedPath
            logger.info(f"tried to import external resource {filePath} but this was already linked to our session directory before. We use the old link: {linkedPath} ")

        elif linkedPathAlreadyExists:
            #A new file shall be imported but it would create a linked name which already exists in our session dir.
            #Because we already checked for a new link to the same file above this means actually linking a different file so we need to differentiate with a unique name
            firstpart, extension = os.path.splitext(linkedPath)
            uniqueLinkedPath = firstpart + "." + uuid4().hex + extension
            assert not os.path.exists(uniqueLinkedPath)
            os.symlink(filePath, uniqueLinkedPath)
            logger.info(self.ourClientNameUnderNSM + f":pysm2: tried to import external resource {filePath} but potential target link {linkedPath} already exists. Linked to {uniqueLinkedPath} instead.")
            linkedPath = uniqueLinkedPath

        else: #this is the "normal" case. External resources will be linked.
            assert not os.path.exists(linkedPath)
            os.symlink(filePath, linkedPath)
            logger.info(f"imported external resource {filePath} as link {linkedPath}")

        assert os.path.exists(linkedPath), linkedPath
        return linkedPath

class NullClient(object):
    """Use this as a drop-in replacement if your program has a mode without NSM but you don't want
    to change the code itself.
    This was originally written for programs that have a core-engine and normal mode of operations
    is a GUI with NSM but they also support commandline-scripts and batch processing.
    For these you don't want NSM."""

    def __init__(self, *args, **kwargs):
        self.realClient = False
        self.ourClientNameUnderNSM = "NSM Null Client"

    def announceSaveStatus(self, *args):
        pass

    def announceGuiVisibility(self, *args):
        pass

    def reactToMessage(self):
        pass

    def importResource(self):
        return ""

    def serverSendExitToSelf(self):
        quit()
