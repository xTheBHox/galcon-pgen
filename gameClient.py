import networkClient as net
import gameServerSide
import pgen
import ai

import threading

import pygame as pg
import pygame.display as disp
import pygame.event as pgevent
import pygame.image as pgi
import pygame.gfxdraw as gfx
import pygame.time as pgtime
import pygame.sprite as sp
import pygame.transform as tf
import pygame.freetype as pgfont

import math

from math import pi
MAPW, MAPH = 768, 768
HELPTEXT = """The objective of this game is to capture all the planets on the \
map.
In order to capture a planet, a certain number of ships have to be sent to \
it. This number is indicated on neutral planets. The number of ships on an \
emeny planet is hidden. Click and drag the left-mouse button from planet to \
planet to send ships. You may also click and drag a group of ships to change \
their destination.
Each planet will spawn new ships once it is captured. Larger planets will \
spawn ships more quickly.
You can see a list of planets and your ships groups in transit on the \
left-hand sidebar.
Good luck!
"""
MAX_PLAYERS, MIN_PLAYERS = 6, 2
LAST_IP = ""

def normalise(angle):
    return (angle + pi) % (2 * pi) - pi

def toPolar(x, y):
    """Converts to polar form."""
    if x == 0 and y == 0: return 0, 0
    r = math.sqrt(x**2 + y**2)
    arg = (- pi / 2 if x == 0 else math.atan(y / x))
    if x < 0 and y <= 0: return r, arg - pi
    elif y < 0 <= x or (x > 0 and y >= 0): return r, arg
    elif x <= 0 < y: return r, arg + pi

def toCarte(r, arg):
    """Converts to cartesian form."""
    x = r * math.cos(arg)
    y = r * math.sin(arg)
    return x, y

def getAngle(x0, y0, x1, y1):
    """Returns angle of pt1 from pt0."""
    d, angle = toPolar(x1 - x0, y1 - y0)
    return angle

def cartePlusPolar(x0, y0, dr, darg):
    """Adds a polar tuple to a cartesian tuple."""
    dx, dy = toCarte(dr, darg)
    return x0 + dx, y0 + dy

def norm(pt1, pt2):
    x1, y1 = pt1
    x2, y2 = pt2
    return ((x1 - x2) ** 2 + (y1- y2) ** 2) ** 0.5

class RectSp(sp.Sprite):
    # this is a dummy rectangle sprite
    def __init__(self, rect):
        super().__init__()
        self.rect = rect

class Program():

    def __init__(self, w, h):
        pg.mixer.init()
        self.w, self.h = w, h
        self.clock = pgtime.Clock()
        self.screen = disp.set_mode((w, h))
        self.running = True
        self.mode = None
        self.server = None
        self.serverThread = None
        self.serverBridge = None

        self.AIThread = None

        self.startMPMenu = None
        self.joinMPMenu = None
        self.preGameMenu = None
        self.helpMenu = None

        self.downloadingMap = False
        self.connecting = False
        self.IP = 'localhost'

        # create the menu beforehand
        self.__createMainMenu__()
        self.__createHelpMenu__()

        self.showMainMenu()

    def run(self):

        while self.running:

            # check events
            for event in pgevent.get():
                if event.type == pg.KEYDOWN:
                    self.keyPressed(event)
                elif event.type == pg.MOUSEMOTION:
                    self.mouseMove(event)
                elif event.type == pg.MOUSEBUTTONDOWN:
                    self.mouseDown(event)
                elif event.type == pg.MOUSEBUTTONUP:
                    self.mouseUp(event)
                elif event.type == pg.QUIT:
                    self.quitGame()

            if not self.running: break
            # step timer
            self.timerFired()

            self.redraw()

            self.clock.tick(30)

    def __createMainMenu__(self):
        self.mainMenu = Menu(self.w, self.h)
        self.mainMenu.starBG()
        butW = 300

        self.mainMenu.addLabel("GALCON PGEN", self.w // 2, 100,
                               font=pgfont.SysFont('Tahoma', 32))
        self.mainMenu.addButton("PLAY VS AI", pg.Rect((self.w - butW) // 2, 250,
                                                butW, 50),
                                self.singlePlayer)
        self.mainMenu.addButton("START MULTIPLAYER",
                                pg.Rect((self.w - butW) // 2, 310, butW, 50),
                                         self.showStartMPMenu)
        self.mainMenu.addButton("JOIN MULTIPLAYER",
                                pg.Rect((self.w - butW) // 2, 370, butW, 50),
                                        self.showJoinMPMenu)
        self.mainMenu.addButton("HELP",
                                pg.Rect((self.w - butW) // 2, 430, butW, 50),
                                        self.showHelp)
        self.mainMenu.addButton("QUIT",
                                pg.Rect((self.w - butW) // 2, 490, butW, 50),
                                        self.quitGame)

    def singlePlayer(self):
        self.serverBridge = ai.FakeServerBridge()
        self.AIThread = threading.Thread(target=ai.runAI,
                                         args=(self.serverBridge,))
        self.AIThread.start()
        self.serverThread = threading.Thread(
                                target=gameServerSide.start,
                                args=(MAPW, MAPH,
                                      self.serverBridge.serverSendMsg,
                                      self.serverBridge.serverGetMsg))
        self.serverThread.start()
        self.startPreGame()

    def __createHelpMenu__(self):
        self.helpMenu = Menu(self.w, self.h)
        self.helpMenu.starBG()
        butW = 300
        self.helpMenu.addMultilineLabel(HELPTEXT, 100, 100, self.w - 200)
        self.helpMenu.addButton("BACK", pg.Rect((self.w - butW) // 2, 500,
                                                butW, 50), self.showMainMenu)

    def showHelp(self):
        self.helpMenu.pressed = None
        self.mode = self.helpMenu
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

    def quitGame(self):
        if isinstance(self.mode, GameUI):
            self.serverBridge.sendMsg(('dc', None))
        self.quitServer()
        self.running = False

    def quitServer(self):
        if self.serverBridge:
            self.serverBridge.disconnect()
            self.serverBridge = None
        if self.server:
            self.server.shutdown()
            self.server = None

    def showMainMenu(self):
        self.quitServer()
        self.mainMenu.pressed = None
        self.mode = self.mainMenu
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

        if not pg.mixer.music.get_busy():
            self.playMusic()

    def playMusic(self):
        pg.mixer.music.load('media/bgm.mp3')
        pg.mixer.music.play(-1)

    def showStartMPMenu(self):
        self.startMPMenu = StartMPMenu(self.w, self.h, self.startServer,
                                       self.startPreGame, self.stopServer)
        self.startMPMenu.pressed = None
        self.mode = self.startMPMenu
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

    def startServer(self):
        s = self.startMPMenu.startServer()
        if s: self.server = s

    def stopServer(self):
        self.showMainMenu()

    def showJoinMPMenu(self):
        self.joinMPMenu = JoinMPMenu(self.w, self.h, self.startPreGame,
                                     self.showMainMenu)
        self.joinMPMenu.pressed = None
        self.mode = self.joinMPMenu
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

    def startPreGame(self):
        self.preGameMenu = PreGameMenu(self.w, self.h, self.startGame,
                                       self.showJoinMPMenu)
        if not self.serverBridge: self.serverBridge = self.mode.serverBridge
        self.preGameMenu.start(self.serverBridge)
        self.mode = self.preGameMenu
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

    def startGame(self, gameMap, teamNo):
        self.mode = GameUI(self.w, self.h, gameMap, teamNo,
                           self.serverBridge, self.endGame)
        self.screen.blit(self.mode.bg, (0, 0))
        disp.update()

    def endGame(self):
        self.serverBridge.sendMsg(('dc', None))
        self.playMusic()
        self.showMainMenu()

    # dispatchers

    def timerFired(self):
        self.mode.timerFired()

    def mouseMove(self, event):
        self.mode.mouseMove(event)

    def mouseDown(self, event):
        self.mode.mouseDown(event)

    def mouseUp(self, event):
        self.mode.mouseUp(event)

    def keyPressed(self, event):
        self.mode.keyPressed(event)

    def redraw(self):
        rects = self.mode.redraw(self.screen)
        disp.update(rects)

class Menu():

    pgfont.init()
    LABELFONT = pgfont.SysFont('Tahoma', 16)
    FONTCOLOR = (0, 255, 0)

    def __init__(self, w, h):
        super().__init__()
        self.w, self.h = w, h
        self.buttons = sp.RenderUpdates()
        self.textBoxDict = dict()
        self.statusBoxDict = dict()
        self.statusBoxes = sp.RenderUpdates()
        self.pressed = None
        self.textBoxActive = None
        self.bg = pg.Surface((w, h))
        self.bg.fill((0, 0, 0))

    def starBG(self):
        self.bg = pgen.genStarBG(self.w, self.h)

    def addButton(self, *args):
        self.buttons.add(Button(*args))

    def addTextBox(self, name, *args, **kwargs):
        newBox = TextBox(*args, **kwargs)
        self.textBoxDict[name] = newBox
        self.buttons.add(newBox)

    def getTextBox(self, name):
        return self.textBoxDict[name].text

    def addLabel(self, text, x, y, font=None, anchor=None):
        if font is None: font = Menu.LABELFONT
        textImage, rt = font.render(text, Menu.FONTCOLOR)
        if anchor == 'N':
            topLeft = x - rt.width // 2, y
        elif anchor == 'W':
            topLeft = x ,y - rt.height // 2
        elif anchor == 'NW':
            topLeft = x, y
        else: # default to center
            topLeft = (x - rt.width // 2,
                       y - rt.height // 2)
        self.bg.blit(textImage, topLeft)

    def addImage(self, img, loc, dims=None):
        if dims is None:
            self.bg.blit(img, loc)
        else:
            dims = tuple(map(int, dims))
            self.bg.blit(tf.scale(img, dims), loc)

    def addMultilineLabel(self, *args, **kwargs):
        mlLabel = MultilineLabel(*args, **kwargs)
        self.bg.blit(mlLabel.image, mlLabel.rect)

    def addStatusBox(self, name, *args, **kwargs):
        newBox = StatusBox(*args, **kwargs)
        self.statusBoxDict[name] = newBox
        self.statusBoxes.add(newBox)

    def updateStatusBox(self, name, *args, **kwargs):
        self.statusBoxDict[name].updateText(*args, **kwargs)

    def timerFired(self):
        pass

    def mouseMove(self, event):
        if self.pressed: return
        for but in self.buttons:
            if but.containsPt(event.pos):
                but.mouseOver()
            else:
                but.unMouseOver()

    def mouseDown(self, event):
        if self.textBoxActive: self.textBoxActive.deactivate()
        if event.button == 1:
            for but in self.buttons:
                if but.containsPt(event.pos):
                    if isinstance(but, Button):
                        self.pressed = but
                        but.press()
                    elif isinstance(but, TextBox):
                        self.textBoxActive = but
                        but.activate()

    def mouseUp(self, event):
        if self.pressed:
            if self.pressed.containsPt(event.pos):
                self.pressed.release()
            else:
                self.pressed.unpress()
                self.pressed = None

    def keyPressed(self, event):
        if self.textBoxActive:
            if event.key == 8: # backspace
                self.textBoxActive.removeText()
            elif event.key == 13:
                self.textBoxActive.enterFn()
            else:
                self.textBoxActive.addText(event.unicode)

    def redraw(self, screen):
        self.statusBoxes.clear(screen, self.bg)
        rects = self.buttons.draw(screen)
        rects += self.statusBoxes.draw(screen)
        return rects

class Button(sp.DirtySprite):

    COLOR = (0, 255, 0)
    COLORO = (0, 63, 0)
    COLORP = (0, 127, 0)

    pgfont.init()
    FONT = pgfont.SysFont('Tahoma', 16)

    def __init__(self, text, rect, fn, args=tuple()):
        super().__init__()
        self.text = text
        self.rect = rect
        self.fn = fn
        self.args = args
        self.imageBase = pg.Surface((rect.width, rect.height))
        self.imageMouseOver = pg.Surface((rect.width, rect.height))
        self.imageMousePress = pg.Surface((rect.width, rect.height))
        self.image = self.imageBase
        self.__createImages__()

        self.pressed = False

    def __createImages__(self):
        textImage, r  = Button.FONT.render(self.text, Button.COLOR)
        textTopLeft = ((self.rect.width - textImage.get_width()) // 2,
                       (self.rect.height - textImage.get_height()) // 2)
        imgRect = self.image.get_rect()
        gfx.rectangle(self.imageBase, imgRect, Button.COLOR)
        self.imageBase.blit(textImage, textTopLeft)
        self.imageMouseOver.fill(Button.COLORO)
        gfx.rectangle(self.imageMouseOver, imgRect, Button.COLOR)
        self.imageMouseOver.blit(textImage, textTopLeft)
        self.imageMousePress.fill(Button.COLORP)
        gfx.rectangle(self.imageMousePress, imgRect, Button.COLOR)
        self.imageMousePress.blit(textImage, textTopLeft)

    def containsPt(self, pt):
        return self.rect.collidepoint(pt)

    def mouseOver(self):
        self.image = self.imageMouseOver

    def unMouseOver(self):
        self.image = self.imageBase

    def press(self):
        self.image = self.imageMousePress
        self.pressed = True

    def unpress(self):
        self.image = self.imageBase
        self.pressed = False

    def release(self):
        self.image = self.imageBase
        if self.pressed: self.fn(*self.args)


class TextBox(sp.DirtySprite):

    COLOR = (0, 0, 255)
    COLORO = (0, 0, 63)
    COLORP = (127, 127, 255)

    pgfont.init()
    FONT = pgfont.SysFont('Tahoma', 20)

    def __init__(self, rect, enterFn=lambda x: None, defaultText=""):
        super().__init__()
        self.text = defaultText
        self.rect = rect
        self.enterFn = enterFn
        self.imageBase = pg.Surface((rect.width, rect.height))
        self.imageMouseOver = pg.Surface((rect.width, rect.height))
        self.imageMousePress = pg.Surface((rect.width, rect.height))
        self.image = self.imageBase
        self.imgRect = self.image.get_rect()
        self.__typingImages__()
        self.__staticImages__()
        self.active = False

    def __staticImages__(self):
        gfx.rectangle(self.imageBase, self.imgRect, TextBox.COLOR)
        self.imageMouseOver.fill(TextBox.COLORO)
        gfx.rectangle(self.imageMouseOver, self.imgRect, TextBox.COLOR)
        if self.text:
            staticTextImage, r = TextBox.FONT.render(self.text, TextBox.COLOR)
            self.imageBase.blit(staticTextImage, self.textTopLeft)
            self.imageMouseOver.blit(staticTextImage, self.textTopLeft)

    def __typingImages__(self):
        self.imageMousePress.fill((0, 0, 0))
        gfx.rectangle(self.imageMousePress, self.imgRect, TextBox.COLORP)
        if self.text:
            textImage, r = TextBox.FONT.render(self.text, TextBox.COLORP)
            self.textTopLeft = ((self.rect.width - textImage.get_width()) // 2,
                           (self.rect.height - textImage.get_height()) // 2)
            self.imageMousePress.blit(textImage, self.textTopLeft)
        self.image = self.imageMousePress

    def containsPt(self, pt):
        return self.rect.collidepoint(pt)

    def mouseOver(self):
        if not self.active: self.image = self.imageMouseOver

    def unMouseOver(self):
        if not self.active: self.image = self.imageBase

    def activate(self):
        self.__typingImages__()
        self.image = self.imageMousePress
        self.active = True

    def addText(self, c):
        self.text += c
        self.__typingImages__()

    def removeText(self):
        if len(self.text) > 0:
            self.text = self.text[:-1]
            self.__typingImages__()

    def clearText(self):
        self.text = ""
        self.__typingImages__()

    def deactivate(self):
        self.__staticImages__()
        self.image = self.imageBase
        self.active = False

class StatusBox(sp.DirtySprite):

    COLOR = (0, 255, 0)
    pgfont.init()
    FONT = pgfont.SysFont('Tahoma', 16)

    def __init__(self, text, x, y, anchor=None, font=None, textColor=None):
        super().__init__()
        self.text = text
        self.x, self.y = x, y
        self.anchor = anchor
        if font is None: self.font = StatusBox.FONT
        else: self.font = font
        if textColor is None: self.textColor = StatusBox.COLOR
        else: self.textColor = textColor
        self.__createImage__()

    def __createImage__(self):
        self.image, r = self.font.render(self.text, self.textColor)
        if self.anchor == 'N':
            topLeft = self.x - self.image.get_width() // 2, self.y
        elif self.anchor == 'W':
            topLeft = self.x , self.y - self.image.get_height() // 2
        elif self.anchor == 'NW':
            topLeft = self.x, self.y
        else: # default to center
            topLeft = (self.x - self.image.get_width() // 2,
                       self.y - self.image.get_height() // 2)
        self.rect = pg.Rect(*topLeft, self.image.get_width(),
                            self.image.get_height())

    def updateText(self, text=None, color=None):
        if text is not None:
            self.text = text
        if color is not None:
            self.textColor = color
        if not (color is None and text is None):
            self.__createImage__()

class MultilineLabel(sp.Sprite):

    COLOR = (0, 255, 0)
    pgfont.init()
    FONT = pgfont.SysFont('Tahoma', 20)
    PARA_MARGIN = 15
    LINE_MARGIN = 5

    def __init__(self, text, x, y, maxW):
        super().__init__()
        self.text = text
        self.x, self.y = x, y
        self.maxW = maxW
        self.__createImage__()

    def __createImage__(self):
        paraList = []
        self.h = 0
        for paragraph in self.text.splitlines():
            sf, h = self.__createParagraphImage__(paragraph)
            paraList.append((sf, h))
            self.h += h + MultilineLabel.PARA_MARGIN
        self.image = pg.Surface((self.maxW, self.h))
        currY = 0
        for sf, h in paraList:
            self.image.blit(sf, (0, currY))
            currY += h + MultilineLabel.PARA_MARGIN

    def __createParagraphImage__(self, text):
        wordList = text.split()
        lineList = []
        lineSfList = []
        h = 0
        nextLine = wordList.pop(0)
        while nextLine:
            currLine, nextLine = nextLine, ""
            while MultilineLabel.FONT.get_rect(currLine).width < self.maxW:
                if not wordList: break
                currLine += " " + wordList.pop(0)
            else:
                currLine, nextLine = currLine.rsplit(" ", 1)
            lineList.append(currLine)
        for l in lineList:
            sf, r = MultilineLabel.FONT.render(l, MultilineLabel.COLOR)
            lineSfList.append((sf, r))
            h += r.height + MultilineLabel.LINE_MARGIN
        image = pg.Surface((self.maxW, h))
        currY = 0
        for sf, r in lineSfList:
            image.blit(sf, (0, currY))
            currY += r.height + MultilineLabel.LINE_MARGIN
        return image, h

    @property
    def rect(self):
        return pg.Rect(self.x, self.y, self.maxW, self.h)

class StartMPMenu(Menu):

    def __init__(self, w, h, serverFn, contFn, backFn):
        super().__init__(w, h)
        self.starBG()
        butW = 300
        self.addLabel("Enter your own IP address:", w // 2, 230)
        self.addTextBox("IP", pg.Rect((w - butW) // 2, 250, butW, 70),
                        self.startServer, defaultText=LAST_IP)
        self.addLabel("Number of players (%d-%d):" % (MIN_PLAYERS, MAX_PLAYERS),
                      w // 2, 350)
        self.addTextBox("players", pg.Rect((w - butW) // 2, 370, butW, 70))
        self.addStatusBox("status", "", w // 2, 480)
        self.addButton("START", pg.Rect((w - butW) // 2, 500, butW, 50),
                                        serverFn)
        self.addButton("BACK", pg.Rect((w - butW) // 2, 560, butW, 50), backFn)
        self.contFn = contFn
        self.serverStarting = False
        self.connectingToSelf = False
        self.waitingForConnect = False
        self.playersConnected = 0
        self.IP = None
        self.server = None
        self.serverBridge = None
        self.numPlayers = 2

    def timerFired(self):
        if self.serverStarting:
            self.checkServerUp()
        elif self.connectingToSelf:
            self.checkConnectSelf()
        elif self.waitingForConnect:
            self.checkConnectionReceived()

    def startServer(self):
        if not (self.serverStarting or self.connectingToSelf or
                self.waitingForConnect):
            self.serverStarting = True
            self.IP = self.getTextBox("IP")
            global LAST_IP
            LAST_IP =  self.IP
            pInput = self.getTextBox("players")
            if not pInput.isdigit():
                self.numPlayers = 2
            else:
                pInput = int(pInput)
                if MIN_PLAYERS <= pInput <= MAX_PLAYERS:
                    self.numPlayers = pInput
            self.updateStatusBox("status",  "Starting server...")
            self.server = net.Server(self.IP, self.numPlayers)
            return self.server

    def checkServerUp(self):
        if self.server.getMsg() == 'serverup':
            self.serverStarting = False
            self.updateStatusBox("status", "Connecting...")
            self.serverBridge = net.ServerBridge(self.IP)
            self.connectingToSelf = True
        elif not self.server.connecting():
            self.serverStarting = False
            self.updateStatusBox("status", "Server start failed.")

    def checkConnectSelf(self):
        if self.serverBridge.getMsg() == 'connected':
            self.connectingToSelf = False
            self.updateStatusBox("status", "Waiting for incoming connection...")
            self.waitingForConnect = True

    def checkConnectionReceived(self):
        msg = self.server.getMsg()
        if  msg == '1connect':
            self.playersConnected += 1
            self.updateStatusBox("status",
                        "Waiting for incoming connection (%d connected)..." %
                                 self.playersConnected)
        elif msg == 'allconnected':
            self.waitingForConnect = False
            self.updateStatusBox("status", "Connection received!")

            # start the actual game server
            self.serverThread = threading.Thread(target=gameServerSide.start,
                             args=(MAPW, MAPH, self.server.broadcast,
                                   self.server.getMsg, self.numPlayers))
            self.serverThread.start()
            self.contFn()

class JoinMPMenu(Menu):

    def __init__(self, w, h, contFn, backFn):
        super().__init__(w, h)
        self.starBG()
        butW = 300
        self.addLabel("Enter the IP address to connect to:", w // 2, 225)
        self.addTextBox("IP", pg.Rect((w - butW) // 2, 250, butW, 100),
                        self.connectToServer, defaultText=LAST_IP)
        self.addStatusBox("status", "", w // 2, 400)
        self.addButton("CONNECT AND START", pg.Rect((w - butW) // 2,
                                                    440, butW, 50),
                       self.connectToServer)
        self.addButton("BACK", pg.Rect((w - butW) // 2, 500, butW, 50),
                       backFn)
        self.contFn = contFn
        self.connecting = False
        self.serverBridge = None

    def timerFired(self):
        if self.connecting:
            self.checkConnected()

    def connectToServer(self):
        self.updateStatusBox("status", "Trying to connect...")
        self.serverBridge = net.ServerBridge(self.getTextBox("IP"))
        global LAST_IP
        LAST_IP =  self.getTextBox("IP")
        self.connecting = True

    def checkConnected(self):
        if self.serverBridge.getMsg() == 'connected':
            self.connecting = False
            self.updateStatusBox("status", "Connected!")
            self.contFn()
        elif not self.serverBridge.connecting():
            self.connecting = False
            self.updateStatusBox("status", "Connection failed.")

class PreGameMenu(Menu):

    def __init__(self, w, h, contFn, backFn, serverBridge=None):
        super().__init__(w, h)
        self.serverBridge = serverBridge
        self.addStatusBox("status", "", w // 2, 400)
        self.contFn = contFn
        self.backFn = backFn
        self.downloadingMap = False
        self.waiting = False
        self.map = None
        self.teamNo = None
        self.numPlanets = None

    def start(self, serverBridge):
        self.serverBridge = serverBridge
        self.downloadingMap = True
        self.updateStatusBox("status", "Waiting for other players...")

    def timerFired(self):
        if not self.serverBridge.connecting():
            self.backFn()
        if self.downloadingMap:
            self.checkMap()
        elif self.waiting:
            self.waitingReady()

    def checkMap(self):
        msg = self.serverBridge.getMsg()
        if isinstance(msg, tuple):
            self.updateStatusBox("status", "Downloading map...")
            t, *contents = msg
            if t == 'tNo':
                self.teamNo = contents[0]
            elif t == 'dims':
                w, h, players, self.numPlanets = contents
                self.map = Map(w, h, players)
            elif t == 'p':
                self.map.addPlanet(*contents)
        if self.map and len(self.map) == self.numPlanets:
            self.downloadingMap = False
            self.serverBridge.sendMsg('ready')
            self.updateStatusBox("status", "Waiting for other players...")
            self.waiting = True

    def waitingReady(self):
        msg = self.serverBridge.getMsg()
        if msg == 'ready':
            self.waiting = False
            self.contFn(self.map, self.teamNo)

class GameUI():

    def __init__(self, w, h, gameMap, teamNo, serverBridge, endFn):
        self.w, self.h = w, h
        self.serverBridge = serverBridge
        self.sbX = gameMap.w
        self.game = Game(gameMap, teamNo, serverBridge)
        self.sb = Sidebar(self.sbX, w, h, self.game, serverBridge)
        self.endFn = endFn
        self.gameOverMsg = GameOverMsg(300, 150, endFn)
        self.mouseDownIn = None
        self.winState = None
        self.gameOver = False

        self.bg = pg.Surface((w, h))
        self.bg.fill((0, 0, 0))
        self.bg.blit(self.sb.bg, (0, 0))
        self.bg.blit(self.game.bg, (0, 0))

    def timerFired(self):
        self.handleServerMsg()
        self.game.timerFired()
        self.sb.timerFired()

    def handleServerMsg(self):
        msg = self.serverBridge.getMsg()
        if msg is not None:
            pkType, *pk = msg
            if pkType == 'gd':
                self.game.handleServerMsg(pkType, pk)
                self.sb.refresh()
            elif pkType == 'gs':
                self.game.handleServerMsg(pkType, pk)
                self.winState = pk[0]
            elif pkType == 'ch':
                self.sb.handleServerMsg(pkType, pk)
            elif pkType == 'eg':
                pg.mixer.music.load('media/gg.mp3')
                pg.mixer.music.play(-1, 6)
                self.endGame()
            elif pkType == 'exit':
                self.sb.handleServerMsg(pkType, pk)

    def mouseMove(self, event):
        self.sb.mouseMove(event)
        if self.gameOver:
            self.gameOverMsg.mouseMove(event)

    def mouseDown(self, event):
        x, y = event.pos
        if self.gameOver and self.gameOverMsg.rect.collidepoint(*event.pos):
            self.mouseDownIn = self.gameOverMsg
            self.gameOverMsg.mouseDown(event)
        elif x > self.sbX:
            self.mouseDownIn = self.sb
            self.sb.mouseDown(event)
        else:
            self.mouseDownIn = self.game
            self.game.mouseDown(event)

    def mouseUp(self, event):
        if self.mouseDownIn is not None:
            self.mouseDownIn.mouseUp(event)
        self.mouseDownIn = None

    def keyPressed(self, event):
        if event.unicode == 't' and self.sb.textBoxActive is None:
            self.sb.textBoxActive = self.sb.textBoxDict['chat']
        else:
            self.sb.keyPressed(event)

    def redraw(self, sc):
        rects = self.sb.redraw(sc)
        rects += self.game.redraw(sc)
        if not self.gameOver:
            return rects
        else:
            self.gameOverMsg.redraw(self.gameOverMsg.bg)
            sc.blit(self.gameOverMsg.bg, self.gameOverMsg.loc)
            return rects + [self.gameOverMsg.rect]

    def endGame(self):
        self.gameOverMsg.show((self.w - 300) // 2, (self.h - 150) // 2,
                              self.winState)
        self.gameOver = True

class GameOverMsg(Menu):

    BOXCOLOR = (0, 255, 0)

    def __init__(self, w, h, menuFn):
        super().__init__(w, h)
        gfx.rectangle(self.bg, self.bg.get_rect(), GameOverMsg.BOXCOLOR)
        self.addStatusBox('msg', "", w//2, h//3)
        butW = (w * 2) // 3
        self.addButton("MAIN MENU", pg.Rect((w - butW)//2, h // 2, butW, h//3),
                       menuFn)
        self.w, self.h = w, h
        self.x, self.y = 0, 0

    def show(self, x, y, win):
        state = 'win' if win == 'W' else 'lose'
        self.updateStatusBox('msg', text="Game over. You %s." % state)
        self.x, self.y = x, y

    @property
    def rect(self):
        return pg.Rect(self.x, self.y, self.w, self.h)

    @property
    def loc(self):
        return self.x, self.y

    def mouseMove(self, event):
        x, y = event.pos
        event.pos = x - self.x, y - self.y
        super().mouseMove(event)

    def mouseDown(self, event):
        x, y = event.pos
        event.pos = x - self.x, y - self.y
        super().mouseDown(event)

    def mouseUp(self, event):
        x, y = event.pos
        event.pos = x - self.x, y - self.y
        super().mouseUp(event)

class Sidebar(Menu):

    pgfont.init()
    HEADERFONT = pgfont.SysFont('Tahoma', 16)
    TEXTFONT = pgfont.SysFont('Tahoma', 14)
    CHFONT = pgfont.SysFont('Tahoma', 12)
    CL_LINES = 8
    CH_LINES = 5

    def __init__(self, x, w, h, game, serverBridge):
        super().__init__(w, h)
        self.x = x
        self.game = game
        self.gameMap = self.game.map
        self.serverBridge = serverBridge
        w -= self.gameMap.w

        marginX, marginY = 3, 2
        # partition the sidebar
        pStart, pEnd = 0, 0.6
        cStart, cEnd = pEnd, 0.8
        mStart, mEnd = cEnd, 1.0

        # make the planet section
        numP = len(self.gameMap)
        pMarginX = marginX
        pMarginY = marginY
        hPerP = ((pEnd - pStart) * h) / (numP + 1) - pMarginY
        self.addLabel('PLANETS', x + w // 2, pStart * h,
                      font=Sidebar.HEADERFONT, anchor='N')
        for i, p in enumerate(self.gameMap):
            top = (i + 1) * (hPerP + pMarginY) + (pStart * h)
            self.addImage(p.image, (x, top), (hPerP, hPerP))
            self.addStatusBox(p.name, p.name, x + hPerP + pMarginX,
                              top + (hPerP // 2), anchor='W',
                              font=Sidebar.TEXTFONT)

        # make the clusters section
        cMarginX = marginX
        cMarginY = marginY
        hPerC = ((cEnd - cStart) * h) / (Sidebar.CL_LINES + 1) - cMarginY
        self.addLabel('GROUPS', x + w // 2, cStart * h,
                      font=Sidebar.HEADERFONT,
                      anchor='N')
        for i in range(Sidebar.CL_LINES):
            top = (i + 1) * (hPerC + cMarginY) + (cStart * h)
            self.addStatusBox('cl' + str(i), "" , x + hPerC + cMarginX,
                              top + (hPerC // 2), anchor='W',
                              font=Sidebar.TEXTFONT)

        # chat and menu section
        mMarginX = marginX
        mMarginY = marginY
        mH = (mEnd - mStart) * h
        chHistH = 0.5
        self.chatHist = [(self.game.teamNo, "Press 't' to chat")]
        for line in range(Sidebar.CH_LINES):
            lineH = chHistH * mH / Sidebar.CH_LINES
            y = (line + 1/2) * lineH + mStart * h
            self.addStatusBox('ch' + str(line), "", x + mMarginX, y,
                              anchor='W', font=Sidebar.CHFONT)

        chBoxStartY, chBoxEndY = 0.5, 0.75
        ggButStartY, ggButEndY = chBoxEndY, 1.0
        chButStartX = 0.75
        self.addTextBox('chat', pg.Rect(x + mMarginX, mStart * h + chHistH * mH,
                                        chButStartX * w - 3 * mMarginX / 2,
                                        (chBoxEndY - chBoxStartY) * mH),
                        self.sendChat)
        self.addButton('CHAT', pg.Rect(x + chButStartX * w + mMarginX / 2,
                                       mStart * h + chHistH * mH,
                                       w - (chButStartX * w + mMarginX * 3/2),
                                       (chBoxEndY - chBoxStartY) * mH),
                       self.sendChat)
        self.addButton('SURRENDER', pg.Rect(x + mMarginX,
                                            mStart * h + ggButStartY * mH,
                                            w - 2 * mMarginX,
                                            (ggButEndY - ggButStartY) * mH),
                       self.lose)

        gfx.line(self.bg, x, 0, x, h, (0, 255, 0))
        self.refreshChat()

    def refresh(self):

        # update the planet list
        for p in self.gameMap:
            if p.needsUpdate:
                if p.teamNo is None:
                    col = Team.NEUTRAL_COLOR
                else:
                    col = Team.teams[p.teamNo].color
                if p.units.count is None:
                    text = p.name
                else:
                    text = p.name + (' (%d)' % p.units.count)
                self.updateStatusBox(p.name, text=text, color=col)
                p.needsUpdate = False

        # update the ships list
        clusters = sorted(filter(lambda t: t[1].teamNo == self.game.teamNo,
                                 iter(self.game.clusterNames.items())),
                          key=lambda t: len(t[1]), reverse=True)
        color = Team.teams[self.game.teamNo].color
        for i in range(Sidebar.CL_LINES):
            if i >= len(clusters):
                self.updateStatusBox('cl' + str(i), text="")
            else:
                name, cl = clusters[i]
                text = "Group %d to %s (%d)" % (name, cl.dest, len(cl))
                self.updateStatusBox('cl' + str(i), text=text, color=color)


    def sendChat(self):
        self.serverBridge.sendMsg(('ch', self.getTextBox('chat')))
        self.textBoxActive = None
        self.textBoxDict['chat'].clearText()

    def refreshChat(self):
        for (pNo, msg), line in zip(self.chatHist,
                                    reversed(range(Sidebar.CH_LINES))):
            self.updateStatusBox('ch' + str(line), text=msg,
                                 color=Team.teams[pNo].color)

    def handleServerMsg(self, pkType, pk):
        if pkType == 'ch':
            self.chatHist.insert(0, pk)
            if len(self.chatHist) > Sidebar.CH_LINES:
                self.chatHist.pop()
            self.refreshChat()
        elif pkType == 'exit':
            self.chatHist.insert(0, (self.game.teamNo, 'Server disconnected.'))

    def lose(self):
        self.serverBridge.sendMsg(('gg', None))

class Game():

    OWNCOLOR = (0, 255, 0)
    OPPCOLOR = (255, 63, 63)

    def __init__(self, gameMap, teamNo, serverBridge):
        self.run = True
        self.serverBridge = serverBridge

        # create teams
        self.teamNo = teamNo
        Team.teams = []
        for i in range(gameMap.players):
            if i == self.teamNo:
                Team(Game.OWNCOLOR)
            else:
                Team()
        self.alive = True

        # start the map
        self.map = gameMap
        # self.bg = pg.Surface((self.map.w, self.map.h))
        # self.bg.fill((0, 0, 0))
        self.bg = pgen.genStarBG(self.map.w, self.map.h)
        self.map.draw(self.bg)

        # make ship containers
        self.ships = sp.RenderUpdates()
        self.clusterNames = dict()

        self.selected = False

    def timerFired(self):

        # remove empty clusters
        emptyClusters = []
        for i in self.clusterNames:
            if not self.clusterNames[i]:
                emptyClusters.append(i)
        for i in emptyClusters:
            self.clusterNames.pop(i)

    def handleServerMsg(self, pkType, pk):
        if pkType == 'gd': # game data
            cDict, pDict = pk

            # do stuff with package
            for pName in pDict:
                self.map.pNameDict[pName].serverUpdate(*pDict[pName])

            for cName in cDict:
                if cName not in self.clusterNames:
                    self.clusterNames[cName]=Cluster(cName)
                self.clusterNames[cName].serverUpdate(self, *cDict[cName])
        elif pkType == 'gs': # game state
            pk = pk[0]
            if pk == 'L':
                self.alive = False
            elif pk == 'W':
                pass

    def keyPressed(self, event):
        pass

    def mouseMove(self, event):
        pass

    def mouseDown(self, event):
        if not self.alive: return
        if event.button == 1:
            for planet in self.map:
                if (planet.teamNo == self.teamNo and
                    planet.containsPt(event.pos)):
                    self.selected = 'p', planet
                    return
            for cName in self.clusterNames:
                cl = self.clusterNames[cName]
                if cl.teamNo == self.teamNo:
                    for unit in cl:
                        if unit.containsPt(event.pos):
                            self.selected = 'c', cl
                            return

    def mouseUp(self, event):
        if event.button == 1:
            if self.selected:
                t, obj = self.selected
                for p in self.map:
                    if p is not obj and p.containsPt(event.pos):
                        if t == 'p':
                            self.serverBridge.sendMsg(('op', obj.name, p.name))
                        elif t == 'c':
                            self.serverBridge.sendMsg(('oc', obj.name, p.name))
                        self.selected = False
                        break

    def redraw(self, sc):
        self.ships.clear(sc, self.bg)
        self.map.pTexts.clear(sc, self.bg)
        shipRects = self.ships.draw(sc)
        textRects = self.map.pTexts.draw(sc)
        return shipRects + textRects

class Map(sp.Group):

    def __init__(self, w, h, players):
        super().__init__()
        self.w, self.h = w, h
        self.players = players
        self.pTexts = sp.RenderUpdates()
        self.pNameDict = dict()

    def addPlanet(self, location, r, img, name=None):
        self.pNameDict[name] = Planet(self, location, r, img, name)

class Planet(sp.Sprite):

    def __init__(self, gameMap, location, r, img, name=None):
        super().__init__(gameMap)
        # init the planet
        self.map = gameMap
        self.x, self.y = location
        self.r = r
        self.name = name
        self.teamNo = None
        self.units = PlanetUnits(self)
        self.map.pTexts.add(self.units)
        self.selected = False
        self.needsUpdate = True
        # create the image
        self.image = pgi.fromstring(img, (self.r * 2 + 1, self.r * 2 + 1),
                                          'RGBA')

    def serverUpdate(self, teamNo, numUnits):
        if self.teamNo != teamNo or self.units.count != numUnits:
            self.teamNo = teamNo
            self.units.count = numUnits
            self.units.serverUpdate()
            self.needsUpdate = True

    @property
    def loc(self):
        return self.x, self.y

    @property
    def rect(self):
        l, t = self.x - self.r, self.y - self.r
        r, b = self.x + self.r, self.y + self.r
        return pg.Rect(l, t, r-l+1, b-t+1)

    @property
    def radius(self):
        return self.r

    def containsPt(self, pt):
        return norm(self.loc, pt) < self.r

class PlanetUnits(sp.DirtySprite):

    AURA = 5  # width of aura around planet
    ALPHA = 159

    def __init__(self, planet, count=None):
        super().__init__()
        self.planet = planet
        self.count = count
        self.__createImage__()

    def serverUpdate(self):
        self.__createImage__()

    def __createImage__(self):
        if self.planet.teamNo is None:
            color = *Team.NEUTRAL_COLOR, 63
        else:
            color = *Team.teams[self.planet.teamNo].color, PlanetUnits.ALPHA
        count = "" if self.count is None else str(self.count)
        r = self.planet.r + PlanetUnits.AURA
        w = h = r * 2 + 1
        self.image = pg.Surface((w, h), flags=pg.SRCALPHA)
        gfx.filled_circle(self.image, r, r, r, color)
        gfx.aacircle(self.image, r, r, r, color)
        self.font = pgfont.SysFont("Comic Sans MS", self.planet.r)
        self.text, rt = self.font.render(count, (0, 0, 0, 255))
        self.image.blit(self.text, (r - self.text.get_width() // 2,
                                    r - self.text.get_height() // 2))

    @property
    def rect(self):
        rect = self.planet.rect
        rect.centerx -= PlanetUnits.AURA
        rect.centery -= PlanetUnits.AURA
        rect.inflate(PlanetUnits.AURA * 2, PlanetUnits.AURA * 2)
        return rect

    @property
    def textRect(self):
        x = self.planet.x - self.text.get_width() // 2
        y = self.planet.y - self.text.get_height() // 2
        return pg.Rect(x, y, self.text.get_width(),
                       self.text.get_height())

class Cluster(sp.RenderUpdates):

    def __init__(self, name, teamNo=None, dest=None):
        super().__init__()
        self.name = name
        self.teamNo = teamNo
        self.dest = dest

    def serverUpdate(self, game, teamNo, dest, ships):
        if teamNo != self.teamNo:
            self.teamNo = teamNo
        if dest != self.dest:
            self.dest = dest
        for unit in self:
            unit.kill()
        for s in ships:
            Ship(teamNo, *s, self, game.ships)

class Ship(sp.DirtySprite):

    RADIUS = 6
    BACKANGLE = pi * 3 / 4
    MARGIN = 0

    def __init__(self, teamNo, pt, angle, *groups):
        super().__init__(*groups)

        self.teamNo = teamNo
        self.x, self.y = pt
        self.angle = angle

        # create image
        self.h = self.w = Ship.RADIUS * 2
        self.imageO = pg.Surface((self.w, self.h), flags=pg.SRCALPHA)
        self.__createImage__()
        self.image = self.imageO
        self.__rotateImage__(angle)

    @property
    def loc(self):
        return self.x, self.y

    # @staticmethod
    @property
    def radius(self):
        return Ship.RADIUS

    def __createImage__(self):
        color = Team.teams[self.teamNo].color
        self.imageO.fill((0, 0, 0, 0))
        x1, y1 = map(lambda x: int(round(x)),
                     cartePlusPolar(Ship.RADIUS, Ship.RADIUS,
                                    Ship.RADIUS, Ship.BACKANGLE))
        x2, y2 = map(lambda x: int(round(x)),
                     cartePlusPolar(Ship.RADIUS, Ship.RADIUS,
                                    Ship.RADIUS, - Ship.BACKANGLE))
        x3, y3 = 2 * Ship.RADIUS, Ship.RADIUS
        gfx.aatrigon(self.imageO, x1, y1, x2, y2, x3, y3, color)

    def __rotateImage__(self, turn):
        self.image = tf.rotate(self.imageO, -math.degrees(turn))

    @property
    def rect(self):
        return pg.Rect(self.x - Ship.RADIUS, self.y - Ship.RADIUS,
                       Ship.RADIUS * 2, Ship.RADIUS * 2)

    def containsPt(self, pt):
        return norm(self.loc, pt) < Ship.RADIUS

    def pts(self, i=0):
        pt1 = cartePlusPolar(*self.loc, Ship.RADIUS, self.angle)
        pt2 = cartePlusPolar(*self.loc,
                             Ship.RADIUS, self.angle + Ship.BACKANGLE)
        pt3 = cartePlusPolar(*self.loc,
                             Ship.RADIUS, self.angle - Ship.BACKANGLE)
        pts = [pt1, pt2, pt3]
        if i == 0: return pts
        else: return pts[i - 1]

class Team():

    teams = []
    NEUTRAL_COLOR = (255, 255, 255)
    SELF_COLOR = (0, 255 ,0)
    COLORS = [(95, 63, 255), (255, 0, 0), (223, 31, 191), (255, 255, 0),
              (0, 255, 255), (255, 159, 0)]

    def __init__(self, color=None):
        self.number = len(Team.teams)
        self.color = Team.COLORS[self.number] if color is None else color
        Team.teams.append(self)

def main():
    w, h = 1024, 768
    prog = Program(w, h)
    prog.run()

if __name__ == '__main__':
    main()