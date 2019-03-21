import os
import unittest
import lambda_function as l


class LambdaTests(unittest.TestCase):

    def test_get_mediapackage_password(self):
        # Asset KeyError is raised since I have no ENV Variables for this function.
        self.assertRaises(KeyError, l.get_mediapackage_password)

    def test_send_to_mediapackage(self):
        self.assertRaises(KeyError, l.send_to_mediapackage, 'testname', 'testdata')

    def test_send_file_to_mediapackage(self):
        # Make a testfile
        with open('testfile', 'w+') as f:
            f.write('testinformation')
        # Run test. MediaPackage environment variables not setup.
        self.assertRaises(KeyError, l.send_file_to_mediapackage, 'testfile', True)
        # remove testfile.
        os.remove('testfile')

    def test_make_random_string(self):
        self.assertTrue(type(l.make_random_string()) is str)


if __name__ == '__main__':
    unittest.main()