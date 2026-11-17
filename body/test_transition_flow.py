import unittest
from transition_flow import TransitionFlow

class FlowTests(unittest.TestCase):
    def test_normal_chain_holds_each_endpoint(self):
        f=TransitionFlow()
        for source,target in [('idle','listening'),('listening','thinking'),('thinking','speaking'),('speaking','idle')]:
            self.assertEqual(f.request(target)[:2],(source,target))
            self.assertIsNone(f.finish())
            self.assertEqual(f.node,target)
            self.assertIsNone(f.request(target))

    def test_latest_request_without_obsolete_queue(self):
        f=TransitionFlow();f.request('listening')
        f.request('thinking');f.request('speaking');f.request('idle')
        self.assertEqual(f.finish()[:2],('listening','idle'))
        self.assertIsNone(f.finish())
        self.assertEqual(f.node,'idle')

    def test_missing_stage_routes_via_matching_endpoints(self):
        f=TransitionFlow()
        edges=[f.request('speaking')[:2],f.finish()[:2],f.finish()[:2]]
        self.assertEqual(edges,[('idle','listening'),('listening','thinking'),('thinking','speaking')])
        self.assertIsNone(f.finish())

    def test_thinking_cancel_and_abort(self):
        f=TransitionFlow();f.request('thinking');f.finish();f.finish()
        self.assertEqual(f.request('idle')[:2],('thinking','listening'))
        self.assertEqual(f.finish()[:2],('listening','idle'))
        f.abort();self.assertIsNone(f.active);self.assertEqual(f.node,'idle')

if __name__=='__main__':unittest.main()
