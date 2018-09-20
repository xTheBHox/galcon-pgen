import os
import random
import re

DIRECTORY = "nameDicts"
DEFAULTFILE = "default.txt"

def generatePlanetNames(pMap, fileName=None):

    nameList = list(set(getNameList(len(pMap), fileName)))
    random.shuffle(nameList)
    nameDict = dict()
    for i, planet in enumerate(pMap):
        nameDict[nameList[i]] = planet
        planet.name(nameList[i])
    return nameDict

def getNameList(numNames, fileName=None):

    dicts = os.listdir(DIRECTORY)
    if fileName is None:
        nameRE = re.compile(r'\A\d* ')
        longEnough = [f for f in dicts
                      if re.match(nameRE, f) and
                      int(f.split()[0]) >= numNames]
        if not longEnough: return getDefaultNames(numNames)
        fileName = random.choice(longEnough)

        with open(DIRECTORY + os.sep + fileName) as f:
            names = [line.strip() for line in f.readlines()]

    elif fileName in dicts:
        length = int(fileName.split()[0])

        with open(DIRECTORY + os.sep + fileName) as f:
            names = [line.strip() for line in f.readlines()]
        if numNames > length:
            names += getDefaultNames(numNames-length)

    else: names = getDefaultNames(numNames)

    return names

def getDefaultNames(n):
    with open(DIRECTORY + os.sep + DEFAULTFILE) as f:
        names = random.sample(f.readlines(), n)
    return [n.strip() for n in names]