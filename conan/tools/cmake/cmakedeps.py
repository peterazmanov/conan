import os
import textwrap

from jinja2 import Template

from conans.errors import ConanException
from conans.util.files import save

conan_message = textwrap.dedent("""
    function(conan_message MESSAGE_OUTPUT)
        if(NOT CONAN_CMAKE_SILENT_OUTPUT)
            message(${ARGV${0}})
        endif()
    endfunction()
    """)


apple_frameworks_macro = textwrap.dedent("""
   macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
       if(APPLE)
           foreach(_FRAMEWORK ${FRAMEWORKS})
               # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
               find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAME ${_FRAMEWORK} PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
               if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                   list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
               else()
                   message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${FRAMEWORKS_DIRS}")
               endif()
           endforeach()
       endif()
   endmacro()
   """)


conan_package_library_targets = textwrap.dedent("""
   function(conan_package_library_targets libraries package_libdir deps out_libraries out_libraries_target config package_name)
       unset(_CONAN_ACTUAL_TARGETS CACHE)

       foreach(_LIBRARY_NAME ${libraries})
           find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                        NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
           if(CONAN_FOUND_LIBRARY)
               conan_message(DEBUG "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
               list(APPEND _out_libraries ${CONAN_FOUND_LIBRARY})

               # Create a micro-target for each lib/a found
               set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${config})
               if(NOT TARGET ${_LIB_NAME})
                   # Create a micro-target for each lib/a found
                   add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                   set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                   set(_CONAN_ACTUAL_TARGETS ${_CONAN_ACTUAL_TARGETS} ${_LIB_NAME})
               else()
                   conan_message(STATUS "Skipping already existing target: ${_LIB_NAME}")
               endif()
               list(APPEND _out_libraries_target ${_LIB_NAME})
               conan_message(DEBUG "Found: ${CONAN_FOUND_LIBRARY}")
           else()
               conan_message(ERROR "Library ${_LIBRARY_NAME} not found in package")
           endif()
           unset(CONAN_FOUND_LIBRARY CACHE)
       endforeach()

       # Add all dependencies to all targets
       string(REPLACE " " ";" deps_list "${deps}")
       foreach(_CONAN_ACTUAL_TARGET ${_CONAN_ACTUAL_TARGETS})
           set_property(TARGET ${_CONAN_ACTUAL_TARGET} PROPERTY INTERFACE_LINK_LIBRARIES "${deps_list}" APPEND)
       endforeach()

       set(${out_libraries} ${_out_libraries} PARENT_SCOPE)
       set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
   endfunction()
   """)


variables_template = """
set({name}_PACKAGE_FOLDER "{package_folder}")
set({name}_INCLUDE_DIRS{config_suffix} {deps.include_paths})
set({name}_RES_DIRS{config_suffix} {deps.res_paths})
set({name}_DEFINITIONS{config_suffix} {deps.defines})
set({name}_SHARED_LINK_FLAGS{config_suffix} {deps.sharedlinkflags_list})
set({name}_EXE_LINK_FLAGS{config_suffix} {deps.exelinkflags_list})
set({name}_COMPILE_DEFINITIONS{config_suffix} {deps.compile_definitions})
set({name}_COMPILE_OPTIONS_C{config_suffix} {deps.cflags_list})
set({name}_COMPILE_OPTIONS_CXX{config_suffix} {deps.cxxflags_list})
set({name}_LIB_DIRS{config_suffix} {deps.lib_paths})
set({name}_LIBS{config_suffix} {deps.libs})
set({name}_SYSTEM_LIBS{config_suffix} {deps.system_libs})
set({name}_FRAMEWORK_DIRS{config_suffix} {deps.framework_paths})
set({name}_FRAMEWORKS{config_suffix} {deps.frameworks})
set({name}_BUILD_MODULES_PATHS{config_suffix} {deps.build_modules_paths})
set({name}_BUILD_DIRS{config_suffix} {deps.build_paths})
# Missing the dependencies information here
"""


dynamic_variables_template = """

set({name}_COMPILE_OPTIONS{config_suffix}
        "$<$<COMPILE_LANGUAGE:CXX>:${{{name}_COMPILE_OPTIONS_CXX{config_suffix}}}>"
        "$<$<COMPILE_LANGUAGE:C>:${{{name}_COMPILE_OPTIONS_C{config_suffix}}}>")

set({name}_LINKER_FLAGS{config_suffix}
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{{name}_SHARED_LINK_FLAGS{config_suffix}}}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{{name}_SHARED_LINK_FLAGS{config_suffix}}}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{{name}_EXE_LINK_FLAGS{config_suffix}}}>")

set({name}_FRAMEWORKS_FOUND{config_suffix} "") # Will be filled later
conan_find_apple_frameworks({name}_FRAMEWORKS_FOUND{config_suffix} "${{{name}_FRAMEWORKS{config_suffix}}}" "${{{name}_FRAMEWORK_DIRS{config_suffix}}}")

# Gather all the libraries that should be linked to the targets (do not touch existing variables):
set(_{name}_DEPENDENCIES{config_suffix} "${{{name}_FRAMEWORKS_FOUND{config_suffix}}} ${{{name}_SYSTEM_LIBS{config_suffix}}} {deps_names}")

set({name}_LIBRARIES_TARGETS{config_suffix} "") # Will be filled later, if CMake 3
set({name}_LIBRARIES{config_suffix} "") # Will be filled later
conan_package_library_targets("${{{name}_LIBS{config_suffix}}}"           # libraries
                              "${{{name}_LIB_DIRS{config_suffix}}}"       # package_libdir
                              "${{_{name}_DEPENDENCIES{config_suffix}}}"  # deps
                              {name}_LIBRARIES{config_suffix}             # out_libraries
                              {name}_LIBRARIES_TARGETS{config_suffix}     # out_libraries_targets
                              "{config_suffix}"                           # build_type
                              "{name}")                                       # package_name

foreach(_FRAMEWORK ${{{name}_FRAMEWORKS_FOUND{config_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{config_suffix} ${{_FRAMEWORK}})
    list(APPEND {name}_LIBRARIES{config_suffix} ${{_FRAMEWORK}})
endforeach()

foreach(_SYSTEM_LIB ${{{name}_SYSTEM_LIBS{config_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{config_suffix} ${{_SYSTEM_LIB}})
    list(APPEND {name}_LIBRARIES{config_suffix} ${{_SYSTEM_LIB}})
endforeach()

# We need to add our requirements too
set({name}_LIBRARIES_TARGETS{config_suffix} "${{{name}_LIBRARIES_TARGETS{config_suffix}}};{deps_names}")
set({name}_LIBRARIES{config_suffix} "${{{name}_LIBRARIES{config_suffix}}};{deps_names}")

# FIXME: What is the result of this for multi-config? All configs adding themselves to path?
set(CMAKE_MODULE_PATH ${{{name}_BUILD_DIRS{config_suffix}}} ${{CMAKE_MODULE_PATH}})
set(CMAKE_PREFIX_PATH ${{{name}_BUILD_DIRS{config_suffix}}} ${{CMAKE_PREFIX_PATH}})

"""


def find_transitive_dependencies(public_deps_filenames):
    # https://github.com/conan-io/conan/issues/4994
    # https://github.com/conan-io/conan/issues/5040
    find = textwrap.dedent("""
        if(NOT {dep_filename}_FOUND)
            find_dependency({dep_filename} REQUIRED NO_MODULE)
        endif()
        """)
    lines = ["", "# Library dependencies", "include(CMakeFindDependencyMacro)"]
    for dep_filename in public_deps_filenames:
        lines.append(find.format(dep_filename=dep_filename))
    return "\n".join(lines)


class DepsCppCmake(object):

    def __init__(self, cpp_info, package_name, generator_name):

        def join_paths(paths):
            """
            Paths are doubled quoted, and escaped (but spaces)
            e.g: set(LIBFOO_INCLUDE_DIRS "/path/to/included/dir" "/path/to/included/dir2")
            """
            return "\n\t\t\t".join('"${%s_PACKAGE_FOLDER}/%s"' %
                                   (package_name,
                                    p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"'))
                                   for p in paths)

        def join_flags(separator, values):
            # Flags have to be escaped
            return separator.join(v.replace('\\', '\\\\').replace('$', '\\$').replace('"', '\\"')
                                  for v in values)

        def join_defines(values, prefix=""):
            # Defines have to be escaped, included spaces
            return "\n\t\t\t".join('"%s%s"' % (prefix, v.replace('\\', '\\\\').replace('$', '\\$').
                                   replace('"', '\\"'))
                                   for v in values)

        def join_paths_single_var(values):
            """
            semicolon-separated list of dirs:
            e.g: set(LIBFOO_INCLUDE_DIR "/path/to/included/dir;/path/to/included/dir2")
            """
            return '"%s"' % ";".join(p.replace('\\', '/').replace('$', '\\$') for p in values)

        def format_link_flags(link_flags):
            # Trying to mess with - and / => https://github.com/conan-io/conan/issues/8811
            return link_flags

        self.include_paths = join_paths(cpp_info.includedirs)
        self.include_path = join_paths_single_var(cpp_info.includedirs)
        self.lib_paths = join_paths(cpp_info.libdirs)
        self.res_paths = join_paths(cpp_info.resdirs)
        self.bin_paths = join_paths(cpp_info.bindirs)
        self.build_paths = join_paths(cpp_info.builddirs)
        self.src_paths = join_paths(cpp_info.srcdirs)
        self.framework_paths = join_paths(cpp_info.frameworkdirs)
        self.libs = join_flags(" ", cpp_info.libs)
        self.system_libs = join_flags(" ", cpp_info.system_libs)
        self.frameworks = join_flags(" ", cpp_info.frameworks)
        self.defines = join_defines(cpp_info.defines, "-D")
        self.compile_definitions = join_defines(cpp_info.defines)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cxxflags_list = join_flags(";", cpp_info.cxxflags)
        self.cflags_list = join_flags(";", cpp_info.cflags)
        self.sharedlinkflags_list = join_flags(";", format_link_flags(cpp_info.sharedlinkflags))
        self.exelinkflags_list = join_flags(";", format_link_flags(cpp_info.exelinkflags))

        build_modules = cpp_info.get_property("cmake_build_modules", generator_name) or []
        self.build_modules_paths = join_paths(build_modules)


class CMakeDeps(object):
    name = "CMakeDeps"

    config_template = textwrap.dedent("""
        include(${{CMAKE_CURRENT_LIST_DIR}}/cmakedeps_macros.cmake)

        # Requires CMake > 3.15
        if(${{CMAKE_VERSION}} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${{CMAKE_CURRENT_LIST_DIR}}/{filename}Targets.cmake)

        {target_props_block}
        {find_dependencies_block}
        """)

    targets_template = textwrap.dedent("""
        if(NOT TARGET {name}::{name})
            conan_message(STATUS "Target declared: '{{name}}::{{name}}'")
            add_library({name}::{name} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB DATA_FILES "${{_DIR}}/{filename}-*-data.cmake")

        foreach(f ${{DATA_FILES}})
            include(${{f}})
        endforeach()

        file(GLOB CONFIG_FILES "${{_DIR}}/{filename}Target-*.cmake")
        foreach(f ${{CONFIG_FILES}})
            include(${{f}})
        endforeach()
        """)

    # This template takes the "name" of the target name::name and the current config
    target_properties = Template("""
# Assign target properties
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_LINK_LIBRARIES
             $<$<CONFIG:{{build_type}}>:${{'{'}}{{name}}_LIBRARIES_TARGETS{{config_suffix}}}
                                    ${{'{'}}{{name}}_LINKER_FLAGS{{config_suffix}}}> APPEND)
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_INCLUDE_DIRECTORIES
             $<$<CONFIG:{{build_type}}>:${{'{'}}{{name}}_INCLUDE_DIRS{{config_suffix}}}> APPEND)
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_COMPILE_DEFINITIONS
             $<$<CONFIG:{{build_type}}>:${{'{'}}{{name}}_COMPILE_DEFINITIONS{{config_suffix}}}> APPEND)
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_COMPILE_OPTIONS
             $<$<CONFIG:{{build_type}}>:${{'{'}}{{name}}_COMPILE_OPTIONS{{config_suffix}}}> APPEND)
    """)

    # https://gitlab.kitware.com/cmake/cmake/blob/master/Modules/BasicConfigVersion-SameMajorVersion.cmake.in
    config_version_template = textwrap.dedent("""
        set(PACKAGE_VERSION "{version}")

        if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
            set(PACKAGE_VERSION_COMPATIBLE FALSE)
        else()
            if("{version}" MATCHES "^([0-9]+)\\\\.")
                set(CVF_VERSION_MAJOR "${{CMAKE_MATCH_1}}")
            else()
                set(CVF_VERSION_MAJOR "{version}")
            endif()

            if(PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR)
                set(PACKAGE_VERSION_COMPATIBLE TRUE)
            else()
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            endif()

            if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                set(PACKAGE_VERSION_EXACT TRUE)
            endif()
        endif()
        """)

    components_variables_tpl = Template(textwrap.dedent("""\
        ########### AGGREGATED COMPONENTS AND DEPENDENCIES FOR THE MULTI CONFIG #####################
        #############################################################################################

        set({{ pkg_name }}_COMPONENT_NAMES {{ '${'+ pkg_name }}_COMPONENT_NAMES} {{ pkg_components }})
        list(REMOVE_DUPLICATES {{ pkg_name }}_COMPONENT_NAMES)
        set({{ pkg_name }}_FIND_DEPENDENCY_NAMES {{ '${'+ pkg_name }}_FIND_DEPENDENCY_NAMES} {{ public_deps }})
        list(REMOVE_DUPLICATES {{ pkg_name }}_FIND_DEPENDENCY_NAMES)

        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_variables }}
        set({{ pkg_name }}_COMPONENTS{{ config_suffix }} {{ pkg_components }})

        {%- for comp_name, comp in components %}

        ########### COMPONENT {{ comp_name }} VARIABLES #############################################
        set({{ pkg_name }}_PACKAGE_FOLDER "{{ package_folder }}")
        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS{{ config_suffix }} {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_LIB_DIRS{{ config_suffix }} {{ comp.lib_paths }})
        set({{ pkg_name }}_{{ comp_name }}_RES_DIRS{{ config_suffix }} {{ comp.res_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEFINITIONS{{ config_suffix }} {{ comp.defines }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_DEFINITIONS{{ config_suffix }} {{ comp.compile_definitions }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_C{{ config_suffix }} "{{ comp.cflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_CXX{{ config_suffix }} "{{ comp.cxxflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_LIBS{{ config_suffix }} {{ comp.libs }})
        set({{ pkg_name }}_{{ comp_name }}_SYSTEM_LIBS{{ config_suffix }} {{ comp.system_libs }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORK_DIRS{{ config_suffix }} {{ comp.framework_paths }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS{{ config_suffix }} {{ comp.frameworks }})
        set({{ pkg_name }}_{{ comp_name }}_DEPENDENCIES{{ config_suffix }} {{ comp.public_deps }})
        set({{ pkg_name }}_{{ comp_name }}_LINKER_FLAGS{{ config_suffix }}
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{ comp.exelinkflags_list }}>
        )
        {%- endfor %}
    """))

    components_dynamic_variables_tpl = Template(textwrap.dedent("""\
        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_dynamic_variables }}

        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #############

        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS'+config_suffix+'}' }}" "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORK_DIRS'+config_suffix+'}' }}")

        set({{ pkg_name }}_{{ comp_name }}_LIB_TARGETS{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_name }}_NOT_USED{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_FRAMEWORKS_DEPS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_FOUND'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_SYSTEM_LIBS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES'+config_suffix+'}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_name+'_LIBS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }}"
                                      {{ pkg_name }}_{{ comp_name }}_NOT_USED{{ config_suffix }}
                                      {{ pkg_name }}_{{ comp_name }}_LIB_TARGETS{{ config_suffix }}
                                      "{{ config_suffix }}"
                                      "{{ pkg_name }}_{{ comp_name }}")

        set({{ pkg_name }}_{{ comp_name }}_LINK_LIBS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_name+'_LIB_TARGETS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }})

        {%- endfor %}

        ########## GLOBAL TARGET PROPERTIES {{ build_type }} ########################################
        {{ global_targets_props }}

        {%- macro tvalue(pkg_name, comp_name, var, config_suffix) -%}
            {{'${'+pkg_name+'_'+comp_name+'_'+var+config_suffix+'}'}}
        {%- endmacro -%}
        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} TARGET PROPERTIES ######################################
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{build_type}}>:{{tvalue(pkg_name, comp_name, 'LINK_LIBS', config_suffix)}}
                        {{tvalue(pkg_name, comp_name, 'LINKER_FLAGS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{build_type}}>:{{tvalue(pkg_name, comp_name, 'INCLUDE_DIRS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{build_type}}>:{{tvalue(pkg_name, comp_name, 'COMPILE_DEFINITIONS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<CONFIG:{{build_type}}>:
                         {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_C', config_suffix)}}
                         {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_CXX', config_suffix)}}> APPEND)
        set({{ pkg_name }}_{{ comp_name }}_TARGET_PROPERTIES TRUE)

        {%- endfor %}

        """))

    components_targets_tpl = Template(textwrap.dedent("""\
        # Load the debug and release variables
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB DATA_FILES "${_DIR}/{{ pkg_filename }}-*-data.cmake")

        foreach(f ${DATA_FILES})
            include(${f})
        endforeach()

        # Create the targets for all the components
        foreach(_COMPONENT {{ '${' + pkg_name + '_COMPONENT_NAMES' + '}' }} )
            if(NOT TARGET {{ '${_COMPONENT}' }})
                conan_message(STATUS "Target declared: '${_COMPONENT}'")
                add_library({{ '${_COMPONENT}' }} INTERFACE IMPORTED)
            endif()
        endforeach()

        if(NOT TARGET {{ pkg_name }}::{{ pkg_name }})
            conan_message(STATUS "Target declared: '{{ pkg_name }}::{{ pkg_name }}'")
            add_library({{ pkg_name }}::{{ pkg_name }} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB CONFIG_FILES "${_DIR}/{{ pkg_filename }}Target-*.cmake")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()

        if({{ pkg_name }}_FIND_COMPONENTS)
            foreach(_FIND_COMPONENT {{ '${'+pkg_name+'_FIND_COMPONENTS}' }})
                list(FIND {{ pkg_name }}_COMPONENTS{{ config_suffix }} "{{ pkg_name }}::${_FIND_COMPONENT}" _index)
                if(${_index} EQUAL -1)
                    conan_message(FATAL_ERROR "Conan: Component '${_FIND_COMPONENT}' NOT found in package '{{ pkg_name }}'")
                else()
                    conan_message(STATUS "Conan: Component '${_FIND_COMPONENT}' found in package '{{ pkg_name }}'")
                endif()
            endforeach()
        endif()
        """))

    components_config_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/cmakedeps_macros.cmake)
        include(${CMAKE_CURRENT_LIST_DIR}/{{ pkg_filename }}Targets.cmake)
        include(CMakeFindDependencyMacro)

        foreach(_DEPENDENCY {{ '${' + pkg_name + '_FIND_DEPENDENCY_NAMES' + '}' }} )
            if(NOT {{ '${_DEPENDENCY}' }}_FOUND)
                find_dependency({{ '${_DEPENDENCY}' }} REQUIRED NO_MODULE)
            endif()
        endforeach()

        foreach(_BUILD_MODULE {{ '${' + pkg_name + '_BUILD_MODULES_PATHS_' + config_suffix + '}' }} )
            include({{ '${_BUILD_MODULE}' }})
        endforeach()

        """))

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.arch = self._conanfile.settings.get_safe("arch")
        self.configuration = str(self._conanfile.settings.build_type)
        self.configurations = [v for v in conanfile.settings.build_type.values_range if v != "None"]

    """
        def _validate_components(self, cpp_info):

            def _check_component_in_requirements(require):
                if COMPONENT_SCOPE in require:
                    req_name, req_comp_name = require.split(COMPONENT_SCOPE)
                    if req_name == req_comp_name:
                        return
                    if req_comp_name not in self.deps_build_info[req_name].components:
                        raise ConanException("Component '%s' not found in '%s' package requirement"
                                             % (require, req_name))

        for comp_name, comp in cpp_info.components.items():
            for cmp_require in comp.requires:
                _check_component_in_requirements(cmp_require)

        for pkg_require in cpp_info.requires:
            _check_component_in_requirements(pkg_require)
    """

    def _get_components(self, req, requires):
        """Returns a list of (component_name, DepsCppCMake)"""
        ret = []
        sorted_comps = req.new_cpp_info.get_sorted_components()

        for comp_name, comp in sorted_comps.items():
            comp_genname = self.get_component_name(req, comp_name)
            deps_cpp_cmake = DepsCppCmake(comp, self.get_name(req), self.name)
            public_comp_deps = []
            for require in comp.requires:
                if "::" in require:  # Points to a component of a different package
                    pkg, cmp_name = require.split("::")
                    public_comp_deps.append("{}::{}".format(
                        self.get_name(requires[pkg]),
                        self.get_component_name(requires[pkg], cmp_name)))
                else:  # Points to a component of same package
                    public_comp_deps.append("{}::{}".format(self.get_name(req),
                                                            self.get_component_name(req, require)))
            deps_cpp_cmake.public_deps = " ".join(public_comp_deps)
            ret.append((comp_genname, deps_cpp_cmake))
        ret.reverse()
        return ret

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _data_filename(self, pkg_filename):
        data_fname = "{}-{}".format(pkg_filename, self.configuration.lower())
        if self.arch:
            data_fname += "-{}".format(self.arch)
        data_fname += "-data.cmake"
        return data_fname

    def get_name(self, req):
        ret = req.new_cpp_info.get_property("cmake_target_name", self.name)
        if not ret:
            ret = req.cpp_info.get_name("cmake_find_package_multi", default_name=False)
        return ret or req.ref.name

    def get_filename(self, req):
        ret = req.new_cpp_info.get_property("cmake_file_name", self.name)
        if not ret:
            ret = req.cpp_info.get_filename("cmake_find_package_multi", default_name=False)
        return ret or req.ref.name

    def get_component_name(self, req, comp_name):
        if comp_name not in req.new_cpp_info.components:
            if req.ref.name == comp_name:  # foo::foo might be referencing the root cppinfo
                return self.get_name(req)
            raise KeyError(comp_name)
        ret = req.new_cpp_info.components[comp_name].get_property("cmake_target_name", self.name)
        if not ret:
            ret = req.cpp_info.components[comp_name].get_name("cmake_find_package_multi",
                                                              default_name=False)
        return ret or comp_name

    @property
    def content(self):
        ret = {}
        build_type = str(self._conanfile.settings.build_type)
        config_suffix = "_{}".format(self.configuration.upper()) if self.configuration else ""
        ret["cmakedeps_macros.cmake"] = "\n".join([
            conan_message,
            apple_frameworks_macro,
            conan_package_library_targets,
        ])

        host_requires = {r.ref.name: r for r in
                         self._conanfile.dependencies.transitive_host_requires}

        # Iterate all the transitive requires
        for req in host_requires.values():
            pkg_filename = self.get_filename(req)
            pkg_target_name = self.get_name(req)

            _ret = self.get_target_names_and_filenames(req, host_requires)
            dep_target_names, pkg_public_deps_filenames = _ret
            dep_target_names = ';'.join(dep_target_names)
            config_version = self.config_version_template.format(version=req.ref.version)
            ret[self._config_version_filename(pkg_filename)] = config_version
            pfolder = req.package_folder.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')

            components = self._get_components(req, host_requires)
            # Note these are in reversed order, from more dependent to less dependent
            pkg_components = " ".join(["{p}::{c}".format(p=pkg_target_name, c=comp_findname) for
                                       comp_findname, _ in reversed(components)])
            global_cppinfo = req.new_cpp_info.copy()
            global_cppinfo.aggregate_components()
            deps = DepsCppCmake(global_cppinfo, pkg_target_name, self.name)
            global_variables = variables_template.format(name=pkg_target_name, deps=deps,
                                                         package_folder=pfolder,
                                                         config_suffix=config_suffix,
                                                         deps_names=dep_target_names)
            variables = {
                self._data_filename(pkg_filename):
                    self.components_variables_tpl.render(
                     package_folder=pfolder, public_deps=" ".join(pkg_public_deps_filenames),
                     pkg_name=pkg_target_name, global_variables=global_variables,
                     pkg_components=pkg_components, config_suffix=config_suffix, components=components)
            }
            ret.update(variables)
            global_dynamic_variables = dynamic_variables_template.format(
                                        name=pkg_target_name,
                                        config_suffix=config_suffix,
                                        deps_names=dep_target_names)

            global_targets_props = self.target_properties.render(name=pkg_target_name,
                                                                 build_type=build_type,
                                                                 config_suffix=config_suffix)
            dynamic_variables = {
                "{}Target-{}.cmake".format(pkg_filename, build_type.lower()):
                self.components_dynamic_variables_tpl.render(
                    global_targets_props=global_targets_props,
                    pkg_name=pkg_target_name, global_dynamic_variables=global_dynamic_variables,
                    pkg_components=pkg_components, build_type=build_type, components=components,
                    config_suffix=config_suffix)
            }
            ret.update(dynamic_variables)
            targets = self.components_targets_tpl.render(
                pkg_name=pkg_target_name,
                pkg_filename=pkg_filename,
                components=components,
                config_suffix=config_suffix
            )
            ret["{}Targets.cmake".format(pkg_filename)] = targets
            target_config = self.components_config_tpl.render(
                pkg_name=pkg_target_name,
                pkg_filename=pkg_filename,
                components=components,
                pkg_public_deps=pkg_public_deps_filenames,
                config_suffix=config_suffix
            )
            # Check if the XXConfig.cmake exists to keep the first generated configuration
            # to only include the build_modules from the first conan install. The rest of the
            # file is common for the different configurations.
            config_file_path = self._config_filename(pkg_filename)
            if not os.path.exists(config_file_path):
                ret[config_file_path] = target_config
        return ret

    @staticmethod
    def _config_filename(pkg_filename):
        if pkg_filename == pkg_filename.lower():
            return "{}-config.cmake".format(pkg_filename)
        else:
            return "{}Config.cmake".format(pkg_filename)

    @staticmethod
    def _config_version_filename(pkg_filename):
        if pkg_filename == pkg_filename.lower():
            return "{}-config-version.cmake".format(pkg_filename)
        else:
            return "{}ConfigVersion.cmake".format(pkg_filename)

    def get_target_names_and_filenames(self, req, requires):
        """
        Return 2 list:
          - [{foo}::{bar}, ] of the required
          - [foo, var] filenames for the requires
        """
        dep_target_names = []
        pkg_public_deps_filenames = []

        # Get a list of dependencies target names and file names
        # Declared cppinfo.requires or .components[].requires
        if req.new_cpp_info.required_components:
            for dep_name, component_name in req.new_cpp_info.required_components:
                if dep_name:  # External dep
                    filename = self.get_filename(requires[dep_name])
                    if filename not in pkg_public_deps_filenames:
                        pkg_public_deps_filenames.append(filename)
                else:  # Internal dep (no another component)
                    dep_name = req.ref.name
                _name = self.get_name(requires[dep_name])
                try:
                    _cname = self.get_component_name(requires[dep_name], component_name)
                except KeyError:
                    raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                         "package requirement".format(name=dep_name,
                                                                      cname=component_name))
                dep_target_names.append("{}::{}".format(_name, _cname))
        elif req.dependencies.host_requires:
            # Regular external "conanfile.requires" declared, not cpp_info requires
            dep_target_names = ["{p}::{p}".format(p=self.get_name(r))
                                for r in req.dependencies.host_requires]
            pkg_public_deps_filenames = [self.get_filename(r)
                                         for r in req.dependencies.host_requires]
        return dep_target_names, pkg_public_deps_filenames
