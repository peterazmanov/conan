import os

from conans import CMake, tools
from conans.client import join_arguments, defs_to_string
from conans.client.generators.cmake_common_build import cmake_build_template, cmake_build_macros
from conans.paths import CONAN_BUILD_CMAKE


class CMakeRev2(CMake):

    @property
    def command_line(self):
        args = [defs_to_string({"CMAKE_TOOLCHAIN_FILE": CONAN_BUILD_CMAKE}),
                '-Wno-dev']
        return join_arguments(args)

    def write_build_file(self, build_dir):
        contents = self.build_file_contents()
        tools.save(os.path.join(build_dir, CONAN_BUILD_CMAKE), contents)

    def build_file_contents(self):
        lines = []
        if self.generator:
            lines.append('set(CMAKE_GENERATOR "%s" CACHE INTERNAL "" FORCE)' % self.generator)
        if self.toolset:
            lines.append('set(CMAKE_GENERATOR_TOOLSET "%s" CACHE INTERNAL "" FORCE)' % self.toolset)
        for key, value in self.definitions.items():
            lines.append('set(%s "%s")' % (key, value))

        tmp = "\n".join(lines)
        tmp += cmake_build_template
        tmp += cmake_build_macros
        return tmp
