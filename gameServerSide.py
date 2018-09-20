import pgen
import nameGen

import pygame as pg
import pygame.time as pgtime
import pygame.sprite as sp
import pygame.image as pgi
import math
from math import pi
import random as rnd

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

class GameServer():

    def __init__(self, w, h, players, sendFn, recvFn):
        self.w, self.h = w, h
        self.players = players
        self.clock = pgtime.Clock()
        self.recvFn = recvFn
        self.sendFn = sendFn
        self.mode = PreGame(w, h, self.players, self.sendFn, self.startGame)
        self.preGame = self.mode
        self.running = True

    def run(self):

        while self.running:

            self.inputHandler()

            # step timer
            self.timerFired()

            # wait for clock
            if self.mode:
                self.clock.tick(self.mode.fps)
            else:
                self.clock.tick(5)

    def startGame(self):
        self.mode = Game(self.preGame, self.sendFn)

    # dispatchers

    def inputHandler(self):
        msg = self.recvFn()
        while msg is not None:
            self.mode.inputHandler(*msg)
            msg = self.recvFn()

    def timerFired(self):
        if self.mode.timerFired():
            self.running = False

class PreGame():

    def __init__(self, w, h, players, sendFn, startFn):
        self.fps = 5
        self.players = players
        self.sendFn = sendFn
        self.startFn = startFn
        self.map = generateMap(w, h, players)
        self.pNames = nameGen.generatePlanetNames(self.map)
        for p in range(self.players):
            self.sendFn(('tNo', p), p)
        self.map.preGamePackage(sendFn)
        self.ready = [False] * self.players

    def inputHandler(self, pNo, msg):
        if msg == 'ready':
            self.ready[pNo] = True

    def timerFired(self):
        if False not in self.ready:
            self.sendFn('ready')
            self.startFn()

class Game():

    def __init__(self, preGame, sendFn):
        self.run = True
        self.fps = 24
        self.sendFn = sendFn

        # create teams
        self.teams = preGame.players
        self.teamsAlive = [t for t in range(self.teams)]
        self.teamsConnected = [t for t in range(self.teams)]
        self.gameOver = False

        # make the map
        self.planetNames = preGame.pNames
        self.map = preGame.map

        # make ship containers
        self.ships = sp.Group()
        self.clusterNames = dict()

        # set the starting bases
        for i, planet in enumerate(self.map.bases):
            planet.cap(i)

    def inputHandler(self, pNo, msg):

        msgType, *msgBody = msg
        if msgType == 'op':
            target, dest = msgBody
            startPlanet = self.planetNames[target]
            if startPlanet.team == pNo:
                destPlanet = self.planetNames[dest]
                startPlanet.sendShips(self, destPlanet)
        elif msgType == 'oc':
            target, dest = msgBody
            if target in self.clusterNames:
                clust = self.clusterNames[target]
                destPlanet = self.planetNames[dest]
                clust.changeDest(destPlanet)
        elif msgType == 'ch':
            self.sendChat(pNo, msgBody[0])
        elif msgType == 'gg':
            self.sendChat(pNo, 'Player surrendered.')
            self.teamLose(pNo)
        elif msgType == 'dc':
            self.teamDC(pNo)
            if pNo == 0: # host killed the connection!
                self.gameOver = True
                self.teamsConnected = []
        else: print(msg)


    def timerFired(self):

        if self.gameOver:
            if len(self.teamsConnected) == 0:
                return True
            return

        # remove empty clusters
        emptyClusters = []
        for i in self.clusterNames:
            if not self.clusterNames[i]:
                emptyClusters.append(i)
        for i in emptyClusters:
            self.clusterNames.pop(i)

        # move ships
        for i in self.clusterNames:
            self.clusterNames[i].move(self.ships, self.map)

        # check if game over and spawn units
        aliveCheck = {t: False for t in self.teamsAlive}

        for p in self.map:
            # spawn units
            p.spawnTick()

            # while in this loop, might as well check if game is over
            if p.team is not None:
                aliveCheck[p.team] = True

        if False in aliveCheck.values():
            # check if ships surviving
            for i in self.clusterNames:
                aliveCheck[self.clusterNames[i].team] = True

        if False in aliveCheck.values():
            # now these teams have really lost
            self.teamLose(aliveCheck)

        # send game data
        for t in range(self.teams):
            self.sendFn(('gd', self.gameClusterPackage(),
                         self.map.gamePackage(t)), t)

    def sendChat(self, pNo, msg):
        self.sendFn(('ch', pNo, msg))

    def teamLose(self, aliveDict):
        if isinstance(aliveDict, dict):
            for t in aliveDict:
                if not aliveDict[t]:
                    deadTeam = t
        elif isinstance(aliveDict, int):
            deadTeam = aliveDict
        if deadTeam in self.teamsAlive:
            self.teamsAlive.remove(deadTeam)
            self.sendFn(('gs', 'L'), deadTeam)
            self.sendFn(('ch', deadTeam, 'You have lost.'), deadTeam)
        if len(self.teamsAlive) == 1:
            self.endGame()

    def endGame(self):
        winTeam = self.teamsAlive.pop()
        self.sendFn(('gs', 'W'), winTeam)
        self.sendFn(('eg', winTeam))
        self.gameOver = True

    def teamDC(self, teamNo):
        self.sendChat(teamNo, 'Player disconnected.')
        if teamNo in self.teamsAlive:
            self.teamLose(teamNo)
        if teamNo in self.teamsConnected:
            self.teamsConnected.remove(teamNo)


    def gameClusterPackage(self):
        cList = dict()
        for clName in self.clusterNames:
            cList[clName] = self.clusterNames[clName].gamePackage()
        return cList

class Map(sp.Group):

    def __init__(self, w, h, players):
        super().__init__()
        self.w, self.h = w, h
        self.players = players
        self.bases = []

    def addPlanet(self, location, r, img, units):
        newPlanet = Planet(self, location, r, img, units=units)
        if len(self.bases) < self.players:
            self.bases.append(newPlanet)
            newPlanet.units = 20

    def preGamePackage(self, sendFn):
        sendFn(('dims', self.w, self.h, self.players, len(self)))
        for p in self:
            sendFn(('p', p.loc, p.r, pgi.tostring(p.image, 'RGBA'), p.pName))

    def gamePackage(self, t=-1):
        package = dict()
        for p in self:
            if t == -1 or p.team is None or p.team == t:
                package[p.pName] = p.team, p.units
            elif p.team != t:
                package[p.pName] = p.team, None
        return package

class Planet(sp.Sprite):

    SPAWNTIME = 300
    SPAWNCAP = 50

    def __init__(self, gameMap, location, r, img, units=0, pName=None):
        super().__init__(gameMap)
        # init the planet
        self.map = gameMap
        self.x, self.y = location
        self.r = r
        self.spawnRate = r ** 2 // 100
        self.spawnTimer = 0
        self.capped = False
        self.units = units
        self.team = None
        self.selected = False
        self.pName = pName
        # create the image
        self.image = img

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

    def name(self, pName):
        if self.pName is None:
            self.pName = pName

    def closestPoint(self, x, y):
        """Returns the closest point to pt on the planet."""
        angle = getAngle(*self.loc, x, y)
        return cartePlusPolar(*self.loc, self.r, angle)

    def cap(self, newTeam):
        self.team = newTeam
        self.capped = True
        self.spawnTimer = Planet.SPAWNTIME

    def arrival(self, team):
        if self.team == team:
            self.units += 1
        else:
            self.units -= 1
            if self.units < 0:
                self.cap(team)
                self.units = 1

    def spawnTick(self):
        if not self.capped or self.units >= Planet.SPAWNCAP: return
        self.spawnTimer -= self.spawnRate
        if self.spawnTimer <= 0:
            self.units += 1
            self.spawnTimer = Planet.SPAWNTIME

    def containsPt(self, pt):
        return norm(self.loc, pt) < self.r

    def sendShips(self, game, destPlanet):

        # finds available locations around a planet to spawn the
        # ships in a circle around a planet
        BUFFERSPACE = 1
        numShips = self.units // 2

        # create a new group of ships
        cluster = Cluster(destPlanet, self.team)
        game.clusterNames[cluster.name] = cluster

        #initial values
        startAngle = getAngle(*self.loc, *destPlanet.loc)
        spawnDist = self.r + Ship.RADIUS + BUFFERSPACE
        shipsMade = 0
        while shipsMade < numShips:
            angleStep = math.asin((Ship.RADIUS + BUFFERSPACE) / (spawnDist))
            currAngle = startAngle
            while currAngle < pi * 2:
                spawnPt = cartePlusPolar(*self.loc, spawnDist, currAngle)
                tryShip = Ship(spawnPt, self, destPlanet)
                collision = (sp.spritecollideany(tryShip, game.ships,
                                                 Ship.collidedShip) or
                             sp.spritecollideany(tryShip, game.map,
                                                 Ship.collidedShip))
                if collision:
                    # failPoints.append(spawnPt)
                    del tryShip # get rid of failed object
                else:
                    game.ships.add(tryShip)
                    cluster.add(tryShip)
                    shipsMade += 1
                    self.units -= 1
                    if shipsMade == numShips: break
                currAngle += 2 * angleStep

            spawnDist += 2 * Ship.RADIUS + BUFFERSPACE

class Cluster(sp.Group):

    INDEX = 0

    def __init__(self, dest, team):
        super().__init__()
        self.dest = dest
        self.team = team
        self.name = Cluster.INDEX
        Cluster.INDEX += 1

    def move(self, ships, planets):

        def moveUnit(unit, tryTurns):
            for dist in range(Ship.VELOCITY, 0, -1):
                for turn in tryTurns:
                    unit.tryMove(dist, turn)
                    collidePlanet = sp.spritecollideany(unit, planets,
                                                        sp.collide_circle)
                    if collidePlanet is unit.destPlanet:
                        unit.destPlanet.arrival(self.team)
                        unit.kill()
                        return
                    else:
                        pass
                        # moveUnit(unit, filtertryTurns)
                        # return
                    if (len(sp.spritecollide(unit, ships, False,
                                             Ship.collidedShip)) == 1 and
                            not collidePlanet):
                        unit.doMove()
                        return
                    else:
                        unit.unTryMove()

        numTurns = int (Ship.MAXTURN // Ship.TURNANGLE)
        turnList = [i * Ship.TURNANGLE for i in range(- numTurns, numTurns + 1)]
        turnList += [Ship.MAXTURN, -Ship.MAXTURN]

        for unit in self:
            # sorts the possible turns so that the ship tries to go forward
            # first
            tryTurns = sorted(turnList, key=lambda x:
                              abs(x + normalise(unit.offsetAngle)))

            moveUnit(unit, tryTurns)

    def changeDest(self, dest):
        self.dest = dest
        for ship in self:
            ship.destPlanet = dest

    def gamePackage(self):
        ships = []
        for ship in self:
            ships.append((ship.loc, ship.angle))
        return self.team, self.dest.pName, ships

    def checkArrival(self):
        for ship in self:
            if ship.arrive():
                ship.destPlanet.arrival(self.team)
                ship.kill()

class Ship(sp.DirtySprite):

    radius = RADIUS = 6
    BACKANGLE = pi * 3 / 4
    VELOCITY = 3
    MARGIN = 0
    MAXTURN = 0.9 * pi
    TURNANGLE = pi / 6

    def __init__(self, pt, startPlanet, destPlanet, *groups):
        super().__init__(*groups)

        self.team = startPlanet.team
        self.x, self.y = pt
        self.startPlanet = startPlanet
        self.destPlanet = destPlanet

        # create image
        self.h = self.w = Ship.RADIUS * 2
        self.angle = self.angleToDest

        # for collision detection purposes
        self.oldX, self.oldY = 0, 0
        self.currTurn = 0

    @property
    def loc(self):
        return self.x, self.y

    @property
    def rect(self):
        return pg.Rect(self.x - Ship.RADIUS, self.y - Ship.RADIUS,
                       Ship.RADIUS * 2, Ship.RADIUS * 2)

    def collidedShip(self, other):
        # only for other ships!
        x0, y0 = self.loc
        x1, y1 = other.loc
        return ((x1 - x0) ** 2 + (y1 - y0) ** 2) < (2 * Ship.RADIUS) ** 2

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

    @property
    def angleToDest(self):
        return getAngle(*self.loc, *self.destPlanet.loc)

    @property
    def offsetAngle(self):
        return self.angle - self.angleToDest

    # in the context of pathfinding, will need several parameters:
    # a var tracking the current angle wrt to destination angle
    # a var tracking destination angle
    # vars for trying to move

    def tryMove(self, dist, turn):
        self.currTurn = turn
        self.oldX, self.oldY = self.x, self.y
        self.x, self.y = cartePlusPolar(self.x, self.y, dist,
                                        self.angle + turn)

    def unTryMove(self):
        self.x, self.y = self.oldX, self.oldY

    def doMove(self):
        dist, angle = toPolar(self.x - self.oldX, self.y - self.oldY)
        if dist != 0:
            if abs(angle - self.angleToDest) < Ship.TURNANGLE:
                # this gets rid of some wobbling
                angle = self.angleToDest
            self.angle = angle

    def arrive(self):
        return self.destPlanet.containsPt(self.pts(1))

def generateMap(w, h, players=2, planets=17, rMin=20, rMax=40):

    MIN_PLANETS, MAX_PLANETS = 13, 25
    planets = rnd.randint(MIN_PLANETS, MAX_PLANETS)
    newMap = Map(w, h, players)
    mapRect = pg.Rect(0, 0, w, h)

    # adding shine consistently to all the planets
    SHINE_R_MIN, SHINE_R_MAX = 0.1, 0.25
    shineR = rnd.random() * (SHINE_R_MAX - SHINE_R_MIN) + SHINE_R_MIN
    shineAngle = rnd.random() * 2 * pi
    shineX, shineY = toCarte(shineR, shineAngle)

    def getImg(r):
        img = pgen.genRandomPlanetImage(r)
        pgen.shine(img, 0.5 + shineX, 0.5 + shineY)
        pgen.fadeEdges(img, r, 0.8)
        return img

    MAXTRIES = 5 # how many times to try in case of collisions
    MARG = 10 # margin around the planets where there should be no planets
    MAX_ST_U = 20 # maximum and minimum starting units
    MIN_ST_U = 0

    # start with the base planets. Bases will be top vs bottom.
    BS_W, BS_H = 200, 100
    BS_PL_R_VAR = 5 # variation in r for base planet
    BS_ST_U = 20 # starting units
    bsW, bsH = min(BS_W, w), min(BS_H, h // 2)
    bsCX = w // 2
    bsCY = BS_H // 2
    bsRMax = min(rMax, bsW, bsH)
    bsRMin = min(max(rMin, rMax - BS_PL_R_VAR), bsRMax)
    bsR = rnd.randint(bsRMin, bsRMax)
    bsDX = rnd.randint(- BS_W // 2 + bsR, BS_W // 2 - bsR)
    bsDY = rnd.randint(- BS_H // 2 + bsR, BS_H // 2 - bsR)

    newMap.addPlanet((bsCX + bsDX, bsCY + bsDY), bsR, getImg(bsR),
                     BS_ST_U)
    newMap.addPlanet((bsCX + bsDX, h - bsCY - bsDY), bsR, getImg(bsR),
                     BS_ST_U)

    # central planet if odd number of planets
    if planets % 2 == 1:
        planets -= 1
        # odd number of planets means have central planet
        for i in range(MAXTRIES):
            mdX = rnd.randint(rMax, w - rMax)
            mdY = h // 2
            mdR = rnd.randint(rMin, rMax)
            mdRect = RectSp(pg.Rect(mdX - mdR - MARG, mdY - mdR - MARG,
                                    (mdR + MARG) * 2, (mdR + MARG) * 2))
            if not sp.spritecollideany(mdRect, newMap):
                newMap.addPlanet((mdX, mdY), mdR, getImg(mdR),
                                 rnd.randint(MIN_ST_U, MAX_ST_U))
                break

    # want to try to distribute planets around the map a bit

    DISTRIBUTION = 0.5 # proportion to rig
    DEV = 7 # how central the planet should be in the rect
    RIG_R_VAR = 10 # want the rigged planets to be bigger
    # round to nearest power of 4 (probably 4)
    rig = 4 ** int(math.log(int(DISTRIBUTION * planets), 4))
    # divide half the map up into rectangles
    sq = int(math.sqrt(rig))
    rectW, rectH = w // sq, h // sq
    # now just need to check all the rectangles on one side
    for row in range(sq // 2):
        for col in range(sq):
            rect = RectSp(pg.Rect(col * rectW, row * rectH, rectW, rectH))
            if not sp.spritecollideany(rect, newMap):
                # no planets in this rect yet so make some
                for i in range(MAXTRIES):

                    r = rnd.randint(max(rMin, rMax - RIG_R_VAR), rMax)
                    x = pgen.randNormalCutoff(col * rectW, (col + 1) * rectW,
                                              DEV)
                    # the min is to make sure it's not too close to the
                    # center line to prevent collision across it
                    y = pgen.randNormalCutoff(row * rectH,
                    min((row + 1) * rectH, h // 2 - r - MARG // 2), DEV)
                    pRect = RectSp(pg.Rect(x - r - MARG, y - r - MARG,
                                    (r + MARG) * 2, (r + MARG) * 2))
                    if (not sp.spritecollideany(pRect, newMap)
                        and mapRect.contains(pRect.rect)):
                        stU = rnd.randint(MIN_ST_U, MAX_ST_U)
                        newMap.addPlanet((x, y), r, getImg(r), stU)
                        newMap.addPlanet((x, h - y), r, getImg(r), stU)
                        planets -= 2
                        break

    # finally, make the rest of the planets
    for pl in range(planets // 2):
        for i in range(MAXTRIES):
            r = rnd.randint(rMin, rMax)
            x = rnd.randint(r, w - r)
            y = rnd.randint(r, h // 2 - r - MARG)
            pRect = RectSp(pg.Rect(x - r - MARG, y - r - MARG,
                            (r + MARG) * 2, (r + MARG) * 2))
            if (not sp.spritecollideany(pRect, newMap)
                and mapRect.contains(pRect.rect)):
                stU = rnd.randint(MIN_ST_U, MAX_ST_U)
                newMap.addPlanet((x, y), r, getImg(r), stU)
                newMap.addPlanet((x, h - y), r, getImg(r), stU)
                break
    return newMap

def start(w, h, sendFn, recvFn, p=2):
    s = GameServer(w, h, p, sendFn, recvFn)
    s.run()
    print("Game server shutting down!")