import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def setup_client():
    client = TestClient()
    custom_generator = textwrap.dedent("""
        from conans.model import Generator
        from conans import ConanFile
        from conans.model.conan_generator import GeneratorComponentsMixin
        import textwrap
        import os

        class custom_generator(GeneratorComponentsMixin, Generator):
            name = "custom_generator"
            @property
            def filename(self):
                return "my-generator.txt"

            def _get_components(self, pkg_name, cpp_info):
                components = super(custom_generator, self)._get_components(pkg_name, cpp_info)
                ret = []
                for comp_genname, comp, comp_requires_gennames in components:
                    ret.append("{}:{}".format(comp.name, comp_genname))
                return ret

            @property
            def content(self):
                info = []
                for pkg_name, cpp_info in self.deps_build_info.dependencies:
                    info.append("{}:{}".format(pkg_name, cpp_info.get_property("names", self.name)))
                    info.extend(self._get_components(pkg_name, cpp_info))
                return os.linesep.join(info)
        """)
    client.save({"custom_generator.py": custom_generator})
    client.run("config install custom_generator.py -tf generators")

    client.save({"consumer.py": GenConanfile("consumer", "1.0").with_requires("mypkg/1.0").
                with_generator("custom_generator").with_generator("cmake_find_package")})
    return client


@pytest.mark.tool_cmake
def test_same_results_components(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].set_property("names", "mycomponent-name")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")

    client.run("install consumer.py --build missing")

    with open(os.path.join(client.current_folder, "my-generator.txt")) as custom_gen_file:
        assert "mycomponent:mycomponent-name" in custom_gen_file.read()

    with open(os.path.join(client.current_folder, "Findmypkg.cmake")) as properties_package_file:
        properties_find_package_content = properties_package_file.read()

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].names["cmake_find_package"] = "mycomponent-name"
                self.cpp_info.components["mycomponent"].names["custom_generator"] = "mycomponent-name"
        """)
    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")
    client.run("install consumer.py")

    with open(os.path.join(client.current_folder, "my-generator.txt")) as custom_gen_file:
        assert "mycomponent:mycomponent-name" in custom_gen_file.read()

    with open(os.path.join(client.current_folder, "Findmypkg.cmake")) as find_package_file:
        normal_find_package_content = find_package_file.read()

    assert properties_find_package_content == normal_find_package_content


@pytest.mark.tool_cmake
def test_same_results_without_components(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.set_property("names", "mypkg-name")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")

    client.run("install consumer.py --build missing")

    with open(os.path.join(client.current_folder, "my-generator.txt")) as custom_gen_file:
        assert "mypkg:mypkg-name" in custom_gen_file.read()

    with open(os.path.join(client.current_folder, "Findmypkg.cmake")) as properties_package_file:
        properties_find_package_content = properties_package_file.read()

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.names["cmake_find_package"] = "mypkg-name"
                self.cpp_info.names["custom_generator"] = "mypkg-name"
        """)
    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")
    client.run("install consumer.py")

    with open(os.path.join(client.current_folder, "my-generator.txt")) as custom_gen_file:
        assert "mypkg:mypkg-name" in custom_gen_file.read()

    with open(os.path.join(client.current_folder, "Findmypkg.cmake")) as find_package_file:
        normal_find_package_content = find_package_file.read()

    assert properties_find_package_content == normal_find_package_content
