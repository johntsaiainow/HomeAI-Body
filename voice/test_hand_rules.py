import math
import unittest
from types import SimpleNamespace
from hand_rules import classify


def hand(tips=(.2,.3,.7,.8),mirror=False,rotation=0):
    points=[(.5,1.)]*21
    for i,p in enumerate([(.5,1),(.15,.95),(.08,.9),(.04,.85),(0,.8)]):points[i]=p
    for base,x,tip in zip((5,9,13,17),(.2,.4,.7,.85),tips):
        for offset,t in enumerate((0,.4,.7,1)):
            points[base+offset]=(x+(tip-x)*t,.65-.55*t)
    result=[]
    for x,y in points:
        if mirror:x=1-x
        c,s=math.cos(rotation),math.sin(rotation)
        x,y=(x-.5)*c-(y-.5)*s+.5,(x-.5)*s+(y-.5)*c+.5
        result.append(SimpleNamespace(x=x,y=y,z=0))
    return result


class VulcanTests(unittest.TestCase):
    def test_vulcan_exclusive(self):
        for mirror in (False,True):
            for rotation in (0,.3,-.3):
                self.assertEqual(classify(hand(mirror=mirror,rotation=rotation),640,640),{'Vulcan_Salute'})
    def test_open_palm_not_vulcan(self):
        self.assertNotIn('Vulcan_Salute',classify(hand((.05,.35,.65,.95)),640,640))
    def test_four_fingers_together_not_vulcan(self):
        self.assertNotIn('Vulcan_Salute',classify(hand((.35,.45,.55,.65)),640,640))
    def test_invalid(self):
        self.assertEqual(classify([],640,480),set())


if __name__=='__main__':unittest.main()
