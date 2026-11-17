import unittest
from idle_sleep import IdleSleep

class SleepTests(unittest.TestCase):
    def setUp(self):
        self.tick=1000
        self.policy=IdleSleep(clock=lambda:self.tick)

    def test_exact_five_minutes(self):
        self.tick+=299.9
        self.assertFalse(self.policy.poll())
        self.tick+=.1
        self.assertTrue(self.policy.poll())
        self.assertTrue(self.policy.sleeping)
        self.assertFalse(self.policy.poll())

    def test_interaction_wakes_and_restarts_timer(self):
        self.tick+=300;self.policy.poll()
        self.assertTrue(self.policy.touch())
        self.assertFalse(self.policy.sleeping)
        self.tick+=299;self.assertFalse(self.policy.poll())
        self.tick+=1;self.assertTrue(self.policy.poll())

    def test_music_keeps_awake_and_pausing_allows_sleep(self):
        self.tick+=1000
        self.assertFalse(self.policy.poll(music_playing=True))
        self.tick+=299;self.assertFalse(self.policy.poll())
        self.tick+=1;self.assertTrue(self.policy.poll())

    def test_do_not_interrupt_speaking(self):
        self.tick+=300
        self.assertFalse(self.policy.poll(speaking=True))
        self.assertTrue(self.policy.poll(speaking=False))

if __name__=='__main__':unittest.main()
