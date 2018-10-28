import unittest

from conans.server.revision_list import RevisionList


class RevisionListTest(unittest.TestCase):

    def test_model(self):
        rev = RevisionList()
        rev.add_revision("rev1")
        rev.add_revision("rev2")

        dumped = rev.dumps()
        loaded = RevisionList.loads(dumped)
        self.assertEquals(rev, loaded)
        self.assertEquals(loaded.latest_revision().revision, "rev2")

        loaded.remove_revision("rev2")
        self.assertEquals(loaded.latest_revision().revision, "rev1")
        self.assertIsNotNone(loaded.latest_revision().time)
