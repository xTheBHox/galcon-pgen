import queue
import pygame

AIS = 1

RWEIGHT = 10 ** 3 #radius
DWEIGHT = 10 ** -5 #distance from closest owned planets
UWEIGHT = 10 ** -1 #neutral units currently on
TWEIGHT = 2 #units in transit weight
MOVERATE = 2 # AI moves per sec
MINUNITS = 5

def norm(pt1, pt2):
    x1, y1 = pt1
    x2, y2 = pt2
    return ((x1 - x2) ** 2 + (y1- y2) ** 2) ** 0.5

class AI():

    def __init__(self, sendFn, recvFn):
        self.sendFn = sendFn
        self.recvFn = recvFn
        self.team = None
        self.numPlanets = None
        self.running = False
        self.gaming = False
        self.clock = pygame.time.Clock()
        self.fps = 30
        self.actionCounter = self.fps // MOVERATE
        self.pDict = dict()
        self.pDistDict = dict()
        self.pWorthDict = dict()
        self.cDict = dict()
        self.pAttackList = set()

    def send(self, msg):
        self.sendFn(msg, self.team)

    def preGameUpdate(self, package):
        if package is None: return
        pkType, *pk = package
        if pkType == 'tNo':
            self.team = pk[0]
        elif pkType == 'dims':
            w, h, pl, self.numPlanets = pk
        elif pkType == 'p':
            loc, r, img, pName = pk
            self.pDict[pName] = AI_Planet(loc, r, pName)
            if len(self.pDict) == self.numPlanets:

                # build the distance dictionary
                for pName, p in self.pDict.items():
                    self.pDistDict[pName] = {op: norm(p.loc, self.pDict[op].loc)
                                             for op in self.pDict
                                             if op is not p}

                self.send('ready')
        elif package == 'ready':
            self.gaming = True

    def serverUpdate(self, package):
        if package is None: return
        pkType, *pk = package
        if pkType == 'gd':
            cPk, pPk = pk
            self.cDict.clear()
            for cName in cPk:
                team, dest, s = cPk[cName]
                self.cDict[cName] = AI_Cluster(team, dest, s)
            for pName in pPk:
                team, units = pPk[pName]
                self.pDict[pName].team = team
                self.pDict[pName].units = units
        elif pkType == 'gs' or pkType == 'eg':
            self.send(('dc', None))
            self.running = False

    def calcBalance(self):

        ai, pl = 0, 0
        for pName in self.pDict:
            if self.pDict[pName].team == self.team:
                ai += self.pDict[pName].r ** 2
            elif self.pDict[pName].team is not None:
                pl += self.pDict[pName].r ** 2
        self.currBalance = (pl - ai) / 300 + MINUNITS
        if self.currBalance < 0: self.currBalance = 0

    def calcWorths(self):

        # calculate the value of all uncaptured planets wrt to captured planets.

        self.pWorthDict.clear()
        for pName in [p for p in self.pDict if self.pDict[p].team == self.team]:
            self.pWorthDict[pName] = dict()
            for otherP in [p for p in self.pDict if self.pDict[p].team !=
                           self.team]:
                oP = self.pDict[otherP]
                # radius contribution
                rW = RWEIGHT / (oP.r ** 2)
                # distance contribution
                dW = self.pDistDict[pName][otherP] ** 2 * DWEIGHT
                # units negative contribution
                uW = (1 / (0.1 + (self.currBalance if oP.units is None else
                                 oP.units - sum(self.cDict[c].numShips
                                      for c in self.cDict
                                      if self.cDict[c].destName == otherP)))
                      * UWEIGHT)
                self.pWorthDict[pName][otherP] = rW + dW - uW

        self.pAttackList = {p for p in self.pAttackList if self.pDict[p].team
                            != self.team}

    def act(self):
        self.calcBalance()
        self.calcWorths()

        if self.currBalance > 25: # probably gg
            self.send(('ch', 'gg'))
            self.send(('gg', None))
        for pName in self.pWorthDict:
            pToAttack = min(self.pWorthDict[pName],
                            key=self.pWorthDict[pName].get)
            if (self.pDict[pToAttack].team is None and
                self.pDict[pName].units > self.pDict[pToAttack].units) or (
                self.pDict[pToAttack].team is not None and
                 self.pDict[pName].units > MINUNITS
                ):
                self.send(('op', pName, pToAttack))
                self.pAttackList.add(pToAttack)
        if self.pAttackList:
            for cName in [c for c in self.cDict if self.cDict[c].team ==
                          self.team]:
                c = self.cDict[cName]
                pToAttack = min(self.pAttackList,
                                key=lambda x: c.avgDistFrom(self.pDict.get(x)))
                if c.destName != pToAttack:
                    self.send(('oc', cName, pToAttack))

    def run(self):

        self.running = True

        while self.running:

            if self.gaming:
                self.serverUpdate(self.recvFn(self.team))
                self.actionCounter -= 1
                if self.actionCounter <= 0:
                    self.act()
                    self.actionCounter = self.fps // MOVERATE
            else:
                self.preGameUpdate(self.recvFn(self.team))

            self.clock.tick(self.fps)

        print("AI closing!")

class AI_Planet():

    def __init__(self, loc, r, pName):
        self.pName = pName
        self.loc = loc
        self.r = r
        self.team = None
        self.units = None

class AI_Cluster():

    def __init__(self, team, destName, ships):
        self.team = team
        self.destName = destName
        self.ships = ships

    @property
    def numShips(self):
        return len(self.ships)

    def avgDistFrom(self, p):
        if len(self.ships) == 0: return 0
        return (sum((norm(p.loc, loc) for loc, angle in self.ships))
                / len(self.ships)
                )

def runAI(serverBridge):
    a = AI(serverBridge.sendMsg, serverBridge.AIGetMsg)
    a.run()

class FakeServerBridge():

    def __init__(self):
        self.serverQ = queue.Queue()
        self.pQList = []
        self.pQList.append(queue.Queue()) # the player queue is queue 0
        self.AITeamsToAssign = []
        for p in range(AIS):
            self.AITeamsToAssign.append(p + 1)
            self.pQList.append(queue.Queue())

    def serverSendMsg(self, msg, pNo=-1):
        if pNo == -1:
            for q in self.pQList:
                q.put(msg)
        else: self.pQList[pNo].put(msg)

    def serverGetMsg(self):
        try:
            msg = self.serverQ.get_nowait()
        except queue.Empty:
            return None
        return msg

    def sendMsg(self, msg, pNo=0):
        self.serverQ.put((pNo, msg))

    def getMsg(self):
        try:
            msg = self.pQList[0].get_nowait()
        except queue.Empty:
            return None
        return msg

    def AIGetMsg(self, AINo):
        if AINo is None: # no team assigned to AI yet
            AINo = self.AITeamsToAssign.pop()
            return 'tNo', AINo
        try:
            msg = self.pQList[AINo].get_nowait()
        except queue.Empty:
            return None
        return msg

    def connecting(self):
        return True

    def disconnect(self):
        pass


