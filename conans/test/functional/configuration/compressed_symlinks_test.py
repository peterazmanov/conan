import os
import platform
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestServer, TurboTestClient
from conans.test.utils.test_files import temp_folder


class CompressSymlinksZeroSize(unittest.TestCase):

    @unittest.skipIf(platform.system() == "Windows", "Better to test only in NIX the symlinks")
    def test_package_symlinks_zero_size(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server})

        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink("file.txt", os.path.join(self.package_folder, "link.txt"))    
"""
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        pref = client.create(ref, conanfile=conanfile)
        # Upload, it will create the tgz
        client.upload_all(ref)

        # We can uncompress it without warns
        p_folder = client.cache.package_layout(pref.ref).package(pref)
        tgz = os.path.join(p_folder, "conan_package.tgz")
        client.run_command('gzip -d "{}"'.format(tgz))
        client.run_command('tar tvf "{}"'.format(os.path.join(p_folder, "conan_package.tar")))
        lines = str(client.out).splitlines()
        """
-rw-r--r-- 0/0               8 1970-01-01 01:00 file.txt
lrw-r--r-- 0/0               0 1970-01-01 01:00 link.txt -> file.txt
        """

        for l in lines:
            if ".txt" not in l:
                continue

            size = int(filter(None, l.split(" "))[2])
            if "link.txt" in l:
                self.assertEqual(int(size), 0)
            elif "file.txt":
                self.assertGreater(int(size), 0)

    @unittest.skipIf(platform.system() == "Windows", "Better to test only in NIX the symlinks")
    def test_no_symlinks_outside_package(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server})
        client.save({"file_not_packaged.txt": "foo"})
        file_path = os.path.join(client.current_folder, "file_not_packaged.txt")
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        os.symlink("{}", os.path.join(self.package_folder, "link.txt"))    
""".format(file_path)
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        pref = client.create(ref, conanfile=conanfile)
        # Upload, it will create the tgz
        client.upload_all(ref)
        p_folder = client.cache.package_layout(pref.ref).package(pref)

        # Check the warning
        msg = "WARN: Symlink of file '{}/link.txt' points to " \
              "'{}' that it is outside the package".format(p_folder, file_path)
        self.assertIn(msg, client.out)

    @unittest.skipIf(platform.system() == "Windows", "Better to test only in NIX the symlinks")
    def test_no_abs_paths_in_package(self):
        server = TestServer()
        client = TurboTestClient(servers={"default": server})
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        tools.save(os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink(os.path.join(self.package_folder, "file.txt"), 
                   os.path.join(self.package_folder, "link.txt"))
"""
        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        # By default it is not allowed
        pref = client.create(ref, conanfile=conanfile)
        # Upload, it will create the tgz
        client.upload_all(ref)
        p_folder = client.cache.package_layout(pref.ref).package(pref)

        # Check the warning
        msg = "WARN: Symlink of file '{}/link.txt' contains an absolute path to '{}/file.txt', " \
              "this path might not exist when the package is installed " \
              "in a different machine".format(p_folder, p_folder)
        self.assertIn(msg, client.out)
