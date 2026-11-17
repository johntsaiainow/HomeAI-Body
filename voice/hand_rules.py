"""Conservative landmark heuristics, not trained gesture probabilities.
Numbers use extended fingers (1=index, 2=index+middle, 3=index+middle+ring).
OK and Pinch overlap physically: remaining three extended -> OK, otherwise Pinch.
"""
import math


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def angle(a, b, c):
    u = [x-y for x,y in zip(a,b)]
    v = [x-y for x,y in zip(c,b)]
    denominator = distance(a,b) * distance(c,b)
    if denominator < 1e-9:
        return 0
    return math.degrees(math.acos(max(-1, min(1, sum(x*y for x,y in zip(u,v))/denominator))))


def classify(hand, width, height):
    if len(hand) != 21:
        return set()
    # Scale normalized coordinates to isotropic image units.
    points = [(p.x * width, p.y * height, p.z * width) for p in hand]
    scale = distance(points[0], points[9])
    if scale < 20:
        return set()
    extended = []
    for base, joint, distal, tip in [(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]:
        straight = angle(points[base],points[joint],points[tip]) > 155
        straight &= angle(points[joint],points[distal],points[tip]) > 150
        straight &= distance(points[0],points[tip]) > distance(points[0],points[joint]) * 1.15
        extended.append(bool(straight))
    thumb = angle(points[1],points[2],points[4]) > 150
    thumb &= angle(points[2],points[3],points[4]) > 150
    thumb &= distance(points[4],points[5]) > scale * 0.5
    contact = distance(points[4],points[8]) / scale
    if contact < 0.25:
        return {'OK' if all(extended[1:]) else 'Pinch'}
    # Vulcan salute: two close finger pairs separated along the palm's
    # lateral axis. Projection avoids mistaking unequal finger lengths for gaps.
    lateral = [points[17][i] - points[5][i] for i in range(3)]
    palm_width = distance(points[5], points[17])
    if all(extended) and palm_width > scale * 0.45:
        positions = [sum(points[tip][i] * lateral[i] for i in range(3)) / palm_width
                     for tip in (8, 12, 16, 20)]
        gaps = [abs(positions[i+1] - positions[i]) / scale for i in range(3)]
        if (gaps[1] > 0.40 and max(gaps[0], gaps[2]) < 0.32
                and gaps[1] > 1.8 * max(gaps[0], gaps[2], 0.05)):
            return {'Vulcan_Salute'}
    patterns = {
        (False, True,False,False,False): 'Number_1',
        (False, True,True,False,False): 'Number_2',
        (False, True,True,True,False): 'Number_3',
        (False, True,True,True,True): 'Number_4',
        (True, True,True,True,True): 'Number_5',
    }
    label = patterns.get((bool(thumb), *extended))
    return {label} if label else set()
