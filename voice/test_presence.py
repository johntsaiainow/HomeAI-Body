"""Deterministic tests; no camera or production log writes."""
import unittest
from perception import Presence


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.tick = 0
        self.events = []
        self.presence = Presence(self.events.append, clock=lambda: self.tick)

    def sample(self, t, names):
        self.tick = t
        self.presence.update(set(names), str(t))

    def appear(self):
        for t in (0, 1, 2):
            self.sample(t, ['cup'])

    def test_transient_and_appearance(self):
        self.sample(0, ['cup'])
        self.sample(1, [])
        self.assertEqual(self.events, [])
        for t in (2, 3, 4):
            self.sample(t, ['cup'])
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0]['first_seen'], '2')

    def test_missed_samples_and_disappearance(self):
        self.appear()
        for t in range(3, 9):
            self.sample(t, [])
        self.sample(9, ['cup'])
        self.assertEqual(len(self.events), 1)
        for t in range(10, 20):
            self.sample(t, [])
        self.assertEqual(len(self.events), 1)
        self.sample(20, [])
        self.assertEqual(len(self.events), 2)
        self.assertEqual(self.events[-1]['last_seen'], '9')

    def test_camera_gap_not_absence(self):
        self.appear()
        self.sample(3, [])
        self.sample(30, [])
        self.sample(31, [])
        self.sample(32, [])
        self.assertEqual(len(self.events), 1)


class NotificationTests(unittest.TestCase):
    def test_chat_cooldown_preserves_structured_events(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        import perception
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(perception, 'ROOT', Path(directory)), \
                 patch.object(perception, 'dialogue') as chat, \
                 patch.object(perception, '_last_object_notice', {}), \
                 patch.object(perception.time, 'monotonic', side_effect=[0, 10]):
                perception.record({'type': 'appeared', 'class_name': 'cup', 'first_seen': 'start'})
                perception.record({'type': 'disappeared', 'class_name': 'cup', 'last_seen': 'end'})
                self.assertEqual(chat.call_count, 1)
                files = list((Path(directory) / 'logs/observations').glob('*.jsonl'))
                events = [json.loads(line) for line in files[0].read_text().splitlines()]
                self.assertEqual(len(events), 2)
                self.assertFalse(events[1]['chat_notified'])


if __name__ == '__main__':
    unittest.main()
