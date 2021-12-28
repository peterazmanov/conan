import types

import pytest
from mock import Mock

from conan.tools.cmake import CMakeToolchain
from conan.tools.cmake.toolchain import Block, GenericSystemBlock
from conans import ConanFile, Settings
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.env_info import EnvValues


@pytest.fixture
def conanfile():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "gcc"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Windows"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_cmake_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "Release"' in content


def test_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks.remove("generic_system")
    content = toolchain.content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_template_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].template = ""
    content = toolchain.content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_template_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"].template
    toolchain.blocks["generic_system"].template = tmp.replace("CMAKE_BUILD_TYPE", "OTHER_THING")
    content = toolchain.content
    assert 'set(OTHER_THING "Release"' in content


def test_context_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"]

    def context(self):
        assert self
        return {"build_type": "SuperRelease"}
    tmp.context = types.MethodType(context, tmp)
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_context_update(conanfile):
    toolchain = CMakeToolchain(conanfile)
    build_type = toolchain.blocks["generic_system"].values["build_type"]
    toolchain.blocks["generic_system"].values["build_type"] = "Super" + build_type
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_context_replace(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].values = {"build_type": "SuperRelease"}
    content = toolchain.content
    assert 'set(CMAKE_BUILD_TYPE "SuperRelease"' in content


def test_replace_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "HelloWorld"

        def context(self):
            return {}

    toolchain.blocks["generic_system"] = MyBlock
    content = toolchain.content
    assert 'HelloWorld' in content
    assert 'CMAKE_BUILD_TYPE' not in content


def test_add_new_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "Hello {{myvar}}!!!"

        def context(self):
            return {"myvar": "World"}

    toolchain.blocks["mynewblock"] = MyBlock
    content = toolchain.content
    assert 'Hello World!!!' in content
    assert 'CMAKE_BUILD_TYPE' in content


def test_user_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["user_toolchain"].values["paths"] = ["myowntoolchain.cmake"]
    content = toolchain.content
    assert 'include("myowntoolchain.cmake")' in content


@pytest.fixture
def conanfile_apple():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": {"Macos": {"version": ["10.15"]}},
                           "compiler": {"apple-clang": {"libcxx": ["libc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "apple-clang"
    c.settings.compiler.libcxx = "libc++"
    c.settings.os = "Macos"
    c.settings.os.version = "10.15"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_osx_deployment_target(conanfile_apple):
    toolchain = CMakeToolchain(conanfile_apple)
    content = toolchain.content
    assert 'set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")' in content


@pytest.fixture
def conanfile_msvc():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": ["Windows"],
                           "compiler": {"msvc": {"version": ["193"], "update": [None],
                                                 "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "msvc"
    c.settings.compiler.version = "193"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Windows"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_toolset(conanfile_msvc):
    toolchain = CMakeToolchain(conanfile_msvc)
    assert 'CMAKE_GENERATOR_TOOLSET "v143"' in toolchain.content
    assert 'Visual Studio 17 2022' in toolchain.generator
    assert 'CMAKE_CXX_STANDARD 20' in toolchain.content


@pytest.fixture
def conanfile_linux():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_no_fpic_when_not_an_option(conanfile_linux):
    toolchain = CMakeToolchain(conanfile_linux)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content


@pytest.fixture
def conanfile_linux_shared():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.options = {
        "fPIC": [True, False],
        "shared": [True, False],
    }
    c.default_options = {"fPIC": False, "shared": True, }
    c.initialize(Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


@pytest.mark.parametrize("fPIC", [True, False])
def test_fpic_when_shared_true(conanfile_linux_shared, fPIC):
    conanfile_linux_shared.options.fPIC = fPIC
    toolchain = CMakeToolchain(conanfile_linux_shared)
    cmake_value = 'ON' if fPIC else 'OFF'
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE {})'.format(cmake_value) in content


def test_fpic_when_not_shared(conanfile_linux_shared):
    conanfile_linux_shared.options.shared = False
    toolchain = CMakeToolchain(conanfile_linux_shared)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' in content


@pytest.fixture
def conanfile_windows_fpic():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.options = {"fPIC": [True, False], }
    c.default_options = {"fPIC": True, }
    c.initialize(Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "gcc"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Windows"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_no_fpic_on_windows(conanfile_windows_fpic):
    toolchain = CMakeToolchain(conanfile_windows_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content


@pytest.fixture
def conanfile_linux_fpic():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.options = {"fPIC": [True, False], }
    c.default_options = {"fPIC": False, }
    c.initialize(Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]}), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    return c


def test_fpic_disabled(conanfile_linux_fpic):
    conanfile_linux_fpic.options.fPIC = False
    toolchain = CMakeToolchain(conanfile_linux_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE OFF' in content


def test_fpic_enabled(conanfile_linux_fpic):
    conanfile_linux_fpic.options.fPIC = True
    toolchain = CMakeToolchain(conanfile_linux_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE ON' in content


def test_libcxx_abi_flag():
    c = ConanFile(Mock(), None)
    c.settings = "os", "compiler", "build_type", "arch"
    c.initialize(Settings.loads(get_default_settings_yml()), EnvValues())
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Linux"
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []

    toolchain = CMakeToolchain(c)
    content = toolchain.content
    assert '-D_GLIBCXX_USE_CXX11_ABI=0' in content
    c.settings.compiler.libcxx = "libstdc++11"
    toolchain = CMakeToolchain(c)
    content = toolchain.content
    # by default, no flag is output anymore, it is assumed the compiler default
    assert 'GLIBCXX_USE_CXX11_ABI' not in content
    # recipe workaround for older distros
    toolchain.blocks["libcxx"].values["glibcxx"] = "1"
    content = toolchain.content
    assert '-D_GLIBCXX_USE_CXX11_ABI=1' in content

    # but maybe the conf is better
    c.conf["tools.gnu:define_libcxx11_abi"] = True
    toolchain = CMakeToolchain(c)
    content = toolchain.content
    assert '-D_GLIBCXX_USE_CXX11_ABI=1' in content
