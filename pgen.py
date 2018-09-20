from random import *
import numpy as np
import math
import bisect
import colorsys
import pygame as pg
import pygame.gfxdraw as gfx
import pygame.surfarray as sfa
import pygame.transform as tf

def callWithLargeStack(f,*args):
    # this function take from course notes
    import sys
    import threading
    threading.stack_size(2**27)  # 64MB stack
    sys.setrecursionlimit(2**27) # will hit 64MB stack limit first
    # need new thread to get the redefined stack size
    def wrappedFn(resultWrapper): resultWrapper[0] = f(*args)
    resultWrapper = [None]
    thread = threading.Thread(target=wrappedFn, args=[resultWrapper])
    thread.start()
    thread.join()
    return resultWrapper[0]

def randNormalCutoff(a, b, dev=4):
    if a > b: a, b = b, a
    delta = gauss(0, b - a / dev)
    if abs(delta) > (b - a) / 2:
        return random() * (b - a) + a
    return (a + b) / 2 + delta

def normalise(tupList):
    names, weights = zip(*tupList)
    total = sum(weights)
    for i in range(len(tupList)):
        tupList[i] = names[i], weights[i] / total

def toCumulative(tup):
    return [sum(tup[:i+1]) for i in range(len(tup))]

def weightedChoice(tupList):
    """Returns a weighted choice from a list containing tuples of the form
    (name, weight)."""
    names, weights = zip(*tupList)
    weights = toCumulative(weights)
    return names[bisect.bisect_left(weights, random())]

def HtoR(h, s, l):
    SCALE = 255
    return tuple(map(lambda x: x * SCALE, colorsys.hls_to_rgb(h, l, s)))

def genColor(hmin=0., hmax=1., smin=0., smax=1., lmin=0., lmax=1.):
    """Generate a random HSL color."""
    HSCALE = 1
    if hmin > hmax: hmin -= HSCALE
    h = (random() * (hmax - hmin) + hmin) % HSCALE
    s = random() * (smax - smin) + smin
    l = random() * (lmax - lmin) + lmin
    return h, s, l

def genColorNormDist(hmin=0., hmax=1., smin=0., smax=1., lmin=0., lmax=1.):
    """Generate a random HSL color with higher probability of being closer
    to center."""
    HSCALE = 1
    if hmin > hmax: hmin -= HSCALE
    params = (hmin, hmax), (smin, smax), (lmin, lmax)
    return tuple(randNormalCutoff(mn, mx) for mn, mx in params)

def gradientLine(l, col1, col2):
    a = np.empty((1, 2, 3), dtype=int)
    a[0][0] = HtoR(*col1)
    a[0][1] = HtoR(*col2)
    return tf.smoothscale(sfa.make_surface(a), (1, l))

def whiteStar(r):
    a = np.full((3, 3, 3), 0, dtype=int)
    a[1][1] = (255, 255, 255)
    # a[1][2] = (255, 255, 255)
    # a[2][1] = (255, 255, 255)
    # a[2][2] = (255, 255, 255)
    return tf.smoothscale(sfa.make_surface(a), (r, r))

def shineCircle(r):
    w = h = r * 2 + 1
    sf = pg.Surface((w, h), flags=pg.SRCALPHA)
    for i in range(r):
        alpha = (255 // r) * (i + 1)
        gfx.filled_circle(sf, r, r, r - i, (255, 255, 255, alpha))
    return sf

def circleFadedEdges(r, startFade):
    w = h = r * 2 + 1
    startR = int(startFade * r)
    sf = pg.Surface((w, h), flags=pg.SRCALPHA)
    for i in range(r - startR):
        alpha = (255 // (r - startR)) * (i + 1)
        gfx.filled_circle(sf, r, r, r - i, (255, 255, 255, alpha))
    return sf

def fadingEllipse(rMaj, rMin, col=(0, 0, 1)):
    col = HtoR(*col)
    w = 2 * rMaj + 1
    h = 2 * rMin + 1
    sf = pg.Surface((w, h), flags=pg.SRCALPHA)
    for i in range(rMaj):
        pc = i / (rMaj)
        alpha = int(pc * 255)
        currMaj = int((1 - pc) * rMaj)
        currMin = int((1 - pc) * rMin)
        gfx.filled_ellipse(sf, rMaj, rMin, currMaj, currMin, (*col, alpha))
    return sf

def planetSolid(r, col1, col2):
    w = h = r * 2 + 1
    sf = pg.Surface((w, h), flags=pg.SRCALPHA)
    tf.scale(gradientLine(h, col1, col2), (w, h), sf)
    cutCircle(sf, r)
    return sf

def genPlanetSolid(r):
    schemeWeights = [('uranus', 1),
                     ('neptune', 0)]
    normalise(schemeWeights)
    bandColorRange1 = {'uranus': (0.08, 0.12, 0.2, 0.5, 0.4, 0.6),
                       'neptune': (0.6, 0.67, 0.9, 1, 0.45, 0.55)}
    scheme = weightedChoice(schemeWeights)
    col = genColor(smax=0.7, lmin=0.4, lmax=0.8)
    otherCol = (coord + gauss(0, 0.08) for coord in col)
    angle = gauss(0, math.pi/6)
    return rotateCircle(planetSolid(r, col, otherCol), angle)

def planetBands(r, bands, smooth=True, sWidth=4):
    """Generates banded circle. bands is an iterable; each element should
    contain (colPair, bandEnd) where colPair is a tuple of colors (for a
    gradient band) and bandEnd is a float indicating the end position of
    the band."""
    w = h = r * 2 + 1
    if not smooth: sWidth = 0
    numBands = len(bands)
    colors, ends = zip(*bands)
    startCols, endCols = [], []
    for colPair in colors:
        if len(colPair) == 2:
            st, en = colPair
            startCols.append(st)
            endCols.append(en)
        else:
            startCols.append(colPair)
            endCols.append(colPair)

    fill = pg.Surface((w, h), flags=pg.SRCALPHA)

    en = 0
    for i in range(numBands):
        st = en + (sWidth * 2 if i > 0 else 0)
        en = int(ends[i] * h) - (sWidth if i < numBands - 1 else 0)
        bH = en - st # band height
        if bH < 0: continue
        band = tf.scale(gradientLine(bH, startCols[i], endCols[i]), (w, bH))
        fill.blit(band, (0, st))

    if smooth:
        for i in range(numBands - 1):
            bH = sWidth * 2 + 2
            band = tf.scale(gradientLine(bH, endCols[i], startCols[i + 1]),
                            (w, bH))
            fill.blit(band, (0, int(ends[i] * h) - sWidth - 1))

    cutCircle(fill, r)
    return fill

def genPlanetBands(r):
    schemeWeights = [('jupiter', 7),
                     ('bluey', 5),
                     ('random', 1)]
    normalise(schemeWeights)
    bandColorRange1 = {'jupiter': (0.08, 0.12, 0.2, 0.5, 0.4, 0.6),
                       'bluey': (0.45, 0.5, 0.85, 0.9, 0.3, 0.4),
                       'random': (0.0, 1.0, 0.2, 0.3, 0.4, 0.5)}
    scheme = weightedChoice(schemeWeights)
    numBands = randint(4, 8)
    bands = []
    for i in range(numBands - 1):
        col = genColor(*bandColorRange1[scheme])
        # offset = gauss(0, 1 / (5 * numBands))
        # while abs(offset) > 1 / (2 * numBands): offset /= 1.1
        # width = (i + 1) * (1 / numBands) + offset
        endPc = (i + 1) * (1 / numBands)
        width = randNormalCutoff(endPc - 1 / (2 * numBands),
                                 endPc + 1 / (2 * numBands))
        bands.append((col, width))
    bands.append((genColor(*bandColorRange1[scheme]), 1))
    angle = gauss(0, math.pi/15)
    return rotateCircle(planetBands(r, bands), angle)

def genLands(r, landCols, seaColRange, lands=10, sizeParam=1.,
             colChangeRate=0.02):
    """Generates a planet with seas and islands."""
    DIRS = ((0, -1), (-1, 0), (0, 1), (1, 0))
    MAXTRIES = 10 # number of times to try to find a land seed
    PROBA, PROBB = 0.49, 1.1 # generation parameters

    if len(seaColRange) == 2: sf = planetSolid(r, *seaColRange)
    else: sf = planetSolid(r, seaColRange, seaColRange)
    randAngle = random() * 2 * math.pi
    sf = rotateCircle(sf, randAngle)
    sizeProb = (PROBA / sizeParam) * (1 - (1 / PROBB ** r))
    landArray = circleMask(r).clip(0, 1)
    sfArray = sfa.pixels3d(sf)
    d = r * 2

    landCols = [HtoR(*col) for col in landCols]

    def joinLands(y, x, landArray, sfArray, col):
        if y < 0 or y > d or x < 0 or x > d or landArray[y][x] != 1: return
        landArray[y][x] = 2
        if random() < colChangeRate: sfArray[y][x] = choice(landCols)
        else: sfArray[y][x] = col
        for dy, dx in DIRS:
            if random() < sizeProb: joinLands(y + dy, x + dx, landArray,
                                              sfArray, col)

    for i in range(lands):
        for j in range(MAXTRIES):
            # find a land seed
            y, x = randint(0, d), randint(0, d)
            if landArray[y][x] == 1: break
        else: continue
        # recursively generate land starting from the seed
        callWithLargeStack(joinLands, x, y, landArray, sfArray,
                           choice(landCols))


    # get rid of 1x1 seas
    h, w = landArray.shape
    for y in range(h):
        for x in range(w):
            if (landArray[y][x] == 1 and
                (x == 0 or landArray[y][x-1] == 2) and
                (y == 0 or landArray[y-1][x] == 2) and
                (x == w-1 or landArray[y][x+1] == 2) and
                (y == h-1 or landArray[y+1][x] == 2)):
                landArray[y][x] = 2
                dy, dx = choice(DIRS)
                if 0 < y < h-1 and 0 < x < w-1:
                    sfArray[y][x] = sfArray[y + dy][x + dx]
    del sfArray
    return sf

def genPlanetLand(r, numLandCols=2):
    schemeWeights = [('green', 5),
                    ('desert', 4),
                    ('mars', 2),
                    ('badland', 2)]
    normalise(schemeWeights)
    seaColorRangeHSL = {'green': (0.6, 0.67, 0.9, 1, 0.45, 0.55),
                        'desert': (0.6, 0.67, 0.9, 1, 0.45, 0.55),
                        'mars': (0.07, 0.1, 0.75, 0.9, 0.4, 0.6),
                        'badland': (0.0, 0.4, 0.05, 0.1, 0.15, 0.3)}
    landColorRangeHSL = {'green': (0.208, 0.375, 0.5, 1.0, 0.15, 0.7),
                         'desert': (0.1, 0.15, 0.5, 0.9, 0.5, 0.6),
                         'mars': (0.0, 0.4, 0.05, 0.1, 0.2, 0.3),
                         'badland': (0.0, 0.4, 0.05, 0.1, 0.05, 0.1)}
    scheme = weightedChoice(schemeWeights)
    seaCol = genColorNormDist(*seaColorRangeHSL[scheme])
    landCols = []
    for col in range(numLandCols):
        landCols.append(genColorNormDist(*landColorRangeHSL[scheme]))
    numLands = randint(7, 10)
    return genLands(r, landCols, seaCol, numLands)

def rotateCircle(sf, angle):
    r = sf.get_width() // 2
    sf = tf.rotate(sf, math.degrees(angle))
    excess = sf.get_width() // 2 - r
    newSf = pg.Surface((r * 2 + 1, r * 2 + 1), flags=pg.SRCALPHA)
    newSf.blit(sf, (0, 0), area=pg.Rect(excess, excess, r * 2, r * 2))
    return newSf

def generatePalette(numColors):
    # generate a starting color
    seedColor = genColor(smin=0.5, smax=0.5, lmin=0.5, lmax=0.5)

def shine(sf, xNorm, yNorm, rNorm=0.4):
    w, h = sf.get_width(), sf.get_height()
    r = int(rNorm * w)
    sf.blit(shineCircle(r), (xNorm * w - r, yNorm * h - r))
    cropCircle(sf, min(w, h) // 2)

def fadeEdges(sf, r, startFade=0.9):
    alphas = sfa.array_alpha(circleFadedEdges(r, startFade))
    a = sfa.pixels_alpha(sf)
    a[:] = alphas
    del a

def spot(sf, col, xNorm, yNorm, rXNorm=0.15, rYNorm=0.08):
    w, h = sf.get_width(), sf.get_height()
    rX, rY = int(rXNorm * w), int(rYNorm * h)
    sf.blit(fadingEllipse(rX, rY, col), (xNorm * w - rX, yNorm * h - rY))

def cropCircle(fill, r):
    alphas = circleMask(r) // 255
    a = sfa.pixels_alpha(fill)
    a *= alphas
    del a

def cutCircle(fill, r):
    cutout = circleMask(r)
    a = sfa.pixels_alpha(fill)
    a[:] = cutout
    del a

def circleMask(r):
    w = h = r * 2 + 1
    sf = pg.Surface((w, h), flags=pg.SRCALPHA)
    gfx.filled_circle(sf, r, r, r, (0, 0, 0, 255))
    return sfa.array_alpha(sf)

def genRandomPlanetImage(r):
    patterns = [('solid', 2),
                    ('bands', 1),
                    ('land', 1)]
    normalise(patterns)
    funcList = {'solid': genPlanetSolid,
                'bands': genPlanetBands,
                'land' : genPlanetLand}
    return funcList[weightedChoice(patterns)](r)

def genStarBG(w, h, stars=None, starRMin=3, starRMax=20, starRVar=0.5):
    if stars is None:
        stars = int(w * h / 10 ** 4)
    MARGIN = 5
    bg = pg.Surface((w, h))
    for s in range(stars):
        x = randint(MARGIN, w - MARGIN)
        y = randint(MARGIN, h - MARGIN)
        r = int(starRMin + expovariate(starRVar))
        if r > starRMax: r = starRMax
        bg.blit(whiteStar(r), (x, y))
    return bg

##### Tests

def testGradientCircle():
    sf = shineCircle(100)
    runTestWindow((sf, 50, 50))

def testFadingEllipse():
    col1 = (0.1, 1, 0.5)
    sf = fadingEllipse(100, 40, col1)
    runTestWindow((sf, 50, 50))

def testBands():
    col1 = (0.1, 1, 0.5)
    col2 = (0.2, 0.7, 0.5)
    # sf = gradientLine(50, (0, 1, 0.5), (0.5, 1, 0.5))
    # sf = planetSolid(20, col1, col2)

    col3 = (0.1, 1, 0.5)
    col4 = (0.2, 0.7, 0.5)
    col5 = (0.1, 1, 0.5)
    col6 = (0.2, 0.7, 0.5)

    sf2 = planetBands(100, (((col1, col2), 0.2),
                            ((col3, col4), 0.8),
                            ((col5, col6), 1)))
    sf = planetBands(100, (((col1, col2), 0.2),
                           ((col3, col4), 0.8),
                           ((col5, col6), 1)),
                     smooth=False)
    runTestWindow((sf2, 10, 10), (sf, 210, 10))

def testShine():
    col1 = (0.1, 0.3, 0.5)
    col2 = (0.2, 0.2, 0.5)
    col3 = (0.1, 0.3, 0.5)
    col4 = (0.2, 0.4, 0.5)
    col5 = (0.2, 0.4, 0.5)
    col6 = (0.2, 0.4, 0.5)

    sf = planetBands(100, (((col1, col2), 0.2),
                           ((col3, col4), 0.8),
                           ((col5, col6), 1)))
    shine(sf, 0.6, 0.3, 0.6)
    runTestWindow((sf, 50, 50))

def testSpot():
    col1 = (0.1, 0.3, 0.5)
    col2 = (0.2, 0.2, 0.5)
    col3 = (0.1, 0.3, 0.5)
    col4 = (0.2, 0.4, 0.5)
    col5 = (0.2, 0.4, 0.5)
    col6 = (0.2, 0.4, 0.5)
    spotCol = (0.05, 0.5, 0.5)

    sf = planetBands(100, (((col1, col2), 0.2),
                           ((col3, col4), 0.8),
                           ((col5, col6), 1)))
    spot(sf, spotCol, 0.3, 0.6, 0.2, 0.1)
    runTestWindow((sf, 50, 50))

def testRotateCircle():
    col1 = (0.1, 0.3, 0.5)
    col2 = (0.2, 0.2, 0.5)
    col3 = (0.1, 0.3, 0.5)
    col4 = (0.2, 0.4, 0.5)
    col5 = (0.2, 0.4, 0.5)
    col6 = (0.2, 0.4, 0.5)

    sf = planetBands(100, (((col1, col2), 0.2),
                           ((col3, col4), 0.8),
                           ((col5, col6), 1)))
    sf = rotateCircle(sf, math.pi/6)
    runTestWindow((sf, 50, 50))

def testGenLands():
    landCols = [(0.3, 1, 0.5),
                (0.33, 0.9, 0.3),
                (0.15, 0.9, 0.6)]
    seaColRange = ((0.65, 1, 0.5), (0.67, 1, 0.5))
    sf = genLands(100, landCols, seaColRange)

    shine(sf, 0.6, 0.3, 0.6)
    runTestWindow((sf, 50, 50))

def testGenLands2():
    landCols = [(0.6, 0.1, 0.2),
                (0.6, 0, 0.15)]
    seaColRange = ((0.6, 0.1, 0.3), (0.6, 0.1, 0.2))
    sf = genLands(100, landCols, seaColRange, sizeParam=0.98)

    shine(sf, 0.6, 0.3, 0.6)
    runTestWindow((sf, 50, 50))

def testGenPlanetLand():
    planets = []
    windowSize = 850
    r = 100
    for i in range(windowSize // (r * 2)):
        for j in range(windowSize // (r * 2)):
            planets.append((genPlanetLand(r), i * 2 * r, j * 2 * r))
    runTestWindow(*planets)

def testGenPlanetBands():
    sf = genPlanetBands(100)
    runTestWindow((sf, 50, 50))

def testGenPlanetSolid():
    sf = genPlanetSolid(100)
    runTestWindow((sf, 50, 50))

def testGenRandomPlanetImage():
    planets = []
    windowSize = 850
    r = 50
    for i in range(windowSize // (r * 2)):
        for j in range(windowSize // (r * 2)):
            p = genRandomPlanetImage(r)
            fadeEdges(p, r)
            shine(p, 0.6, 0.3, 0.6)
            planets.append((p, i * (2 * r + 4), j * (2 * r + 4)))
    runTestWindow(*planets)

def testGenStarBG():
    bg = genStarBG(850, 850, 40)

    runTestWindow((bg, 0, 0))

def runTestWindow(*sfList):
    w, h = 850, 850
    screen = pg.display.set_mode((w, h))
    run = True
    for sf, x, y in sfList:
        screen.blit(sf, (x, y))
    while run:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                run = False
        pg.display.flip()

def main():
    testGenRandomPlanetImage()
    # testGenStarBG()

if __name__ == "__main__":
    main()