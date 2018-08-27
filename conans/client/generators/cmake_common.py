
_cmake_single_dep_vars = """set(CONAN_{dep}_ROOT{build_type} {deps.rootpath})
set(CONAN_INCLUDE_DIRS_{dep}{build_type} {deps.include_paths})
set(CONAN_LIB_DIRS_{dep}{build_type} {deps.lib_paths})
set(CONAN_BIN_DIRS_{dep}{build_type} {deps.bin_paths})
set(CONAN_RES_DIRS_{dep}{build_type} {deps.res_paths})
set(CONAN_BUILD_DIRS_{dep}{build_type} {deps.build_paths})
set(CONAN_LIBS_{dep}{build_type} {deps.libs})
set(CONAN_DEFINES_{dep}{build_type} {deps.defines})
# COMPILE_DEFINITIONS are equal to CONAN_DEFINES without -D, for targets
set(CONAN_COMPILE_DEFINITIONS_{dep}{build_type} {deps.compile_definitions})

set(CONAN_C_FLAGS_{dep}{build_type} "{deps.cflags}")
set(CONAN_CXX_FLAGS_{dep}{build_type} "{deps.cppflags}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type} "{deps.sharedlinkflags}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type} "{deps.exelinkflags}")

# For modern cmake targets we use the list variables (separated with ;)
set(CONAN_C_FLAGS_{dep}{build_type}_LIST "{deps.cflags_list}")
set(CONAN_CXX_FLAGS_{dep}{build_type}_LIST "{deps.cppflags_list}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.sharedlinkflags_list}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.exelinkflags_list}")

"""


def _cmake_string_representation(value):
    """Escapes the specified string for use in a CMake command surrounded with double quotes
       :param value the string to escape"""
    return '"{0}"'.format(value.replace('\\', '\\\\')
                               .replace('$', '\\$')
                               .replace('"', '\\"'))


def _build_type_str(build_type):
    if build_type:
        return "_" + str(build_type).upper()
    return ""


def cmake_user_info_vars(deps_user_info):
    lines = []
    for dep, the_vars in deps_user_info.items():
        for name, value in the_vars.vars.items():
            lines.append('set(CONAN_USER_%s_%s %s)' % (dep.upper(), name, _cmake_string_representation(value)))
    return "\n".join(lines)


def cmake_dependency_vars(name, deps, build_type=""):
    build_type = _build_type_str(build_type)
    return _cmake_single_dep_vars.format(dep=name.upper(), deps=deps, build_type=build_type)


_cmake_package_info = """set(CONAN_PACKAGE_NAME {name})
set(CONAN_PACKAGE_VERSION {version})
"""


def cmake_package_info(name, version):
    return _cmake_package_info.format(name=name, version=version)


def cmake_settings_info(settings):
    settings_info = ""
    for item in settings.items():
        key, value = item
        name = "CONAN_SETTINGS_%s" % key.upper().replace(".", "_")
        settings_info += "set({key} {value})\n".format(key=name, value=_cmake_string_representation(value))
    return settings_info


def cmake_dependencies(dependencies, build_type=""):
    build_type = _build_type_str(build_type)
    dependencies = " ".join(dependencies)
    return "set(CONAN_DEPENDENCIES{build_type} {dependencies})".format(dependencies=dependencies,
                                                                       build_type=build_type)


_cmake_multi_dep_vars = """{cmd_line_args}
set(CONAN_INCLUDE_DIRS{build_type} {deps.include_paths} ${{CONAN_INCLUDE_DIRS{build_type}}})
set(CONAN_LIB_DIRS{build_type} {deps.lib_paths} ${{CONAN_LIB_DIRS{build_type}}})
set(CONAN_BIN_DIRS{build_type} {deps.bin_paths} ${{CONAN_BIN_DIRS{build_type}}})
set(CONAN_RES_DIRS{build_type} {deps.res_paths} ${{CONAN_RES_DIRS{build_type}}})
set(CONAN_LIBS{build_type} {deps.libs} ${{CONAN_LIBS{build_type}}})
set(CONAN_DEFINES{build_type} {deps.defines} ${{CONAN_DEFINES{build_type}}})
set(CONAN_CMAKE_MODULE_PATH{build_type} {deps.build_paths} ${{CONAN_CMAKE_MODULE_PATH{build_type}}})

set(CONAN_CXX_FLAGS{build_type} "{deps.cppflags} ${{CONAN_CXX_FLAGS{build_type}}}")
set(CONAN_SHARED_LINKER_FLAGS{build_type} "{deps.sharedlinkflags} ${{CONAN_SHARED_LINKER_FLAGS{build_type}}}")
set(CONAN_EXE_LINKER_FLAGS{build_type} "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS{build_type}}}")
set(CONAN_C_FLAGS{build_type} "{deps.cflags} ${{CONAN_C_FLAGS{build_type}}}")
"""


def cmake_global_vars(deps, build_type=""):
    if not build_type:
        cmd_line_args = """# Storing original command line args (CMake helper) flags
set(CONAN_CMD_CXX_FLAGS ${CONAN_CXX_FLAGS})

set(CONAN_CMD_SHARED_LINKER_FLAGS ${CONAN_SHARED_LINKER_FLAGS})
set(CONAN_CMD_C_FLAGS ${CONAN_C_FLAGS})
# Defining accumulated conan variables for all deps
"""
    else:
        cmd_line_args = ""
    return _cmake_multi_dep_vars.format(cmd_line_args=cmd_line_args,
                                        deps=deps, build_type=_build_type_str(build_type))


_target_template = """
    conan_package_library_targets("${{CONAN_LIBS_{uname}}}" "${{CONAN_LIB_DIRS_{uname}}}"
                                  CONAN_PACKAGE_TARGETS_{uname} "{deps}" "" {pkg_name})
    conan_package_library_targets("${{CONAN_LIBS_{uname}_DEBUG}}" "${{CONAN_LIB_DIRS_{uname}_DEBUG}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_DEBUG "{deps}" "debug" {pkg_name})
    conan_package_library_targets("${{CONAN_LIBS_{uname}_RELEASE}}" "${{CONAN_LIB_DIRS_{uname}_RELEASE}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_RELEASE "{deps}" "release" {pkg_name})

    add_library({name} INTERFACE IMPORTED)

    # Property INTERFACE_LINK_FLAGS do not work, necessary to add to INTERFACE_LINK_LIBRARIES
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES ${{CONAN_PACKAGE_TARGETS_{uname}}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_LIST}}
                                                                 $<$<CONFIG:Release>:${{CONAN_PACKAGE_TARGETS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:RelWithDebInfo>:${{CONAN_PACKAGE_TARGETS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:MinSizeRel>:${{CONAN_PACKAGE_TARGETS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:Debug>:${{CONAN_PACKAGE_TARGETS_{uname}_DEBUG}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG_LIST}}>
                                                                 {deps})
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES ${{CONAN_INCLUDE_DIRS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_INCLUDE_DIRS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{CONAN_COMPILE_DEFINITIONS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_COMPILE_DEFINITIONS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS ${{CONAN_C_FLAGS_{uname}_LIST}} ${{CONAN_CXX_FLAGS_{uname}_LIST}}
                                                                  $<$<CONFIG:Release>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:RelWithDebInfo>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:MinSizeRel>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:Debug>:${{CONAN_C_FLAGS_{uname}_DEBUG_LIST}}  ${{CONAN_CXX_FLAGS_{uname}_DEBUG_LIST}}>)
 """


def generate_targets_section(dependencies):
    section = []
    section.append("\n###  Definition of macros and functions ###\n")
    section.append('macro(conan_define_targets)\n'
                   '    if(${CMAKE_VERSION} VERSION_LESS "3.1.2")\n'
                   '        message(FATAL_ERROR "TARGETS not supported by your CMake version!")\n'
                   '    endif()  # CMAKE > 3.x\n'
                   '    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CMD_CXX_FLAGS}")\n'
                   '    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_CMD_C_FLAGS}")\n'
                   '    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${CONAN_CMD_SHARED_LINKER_FLAGS}")\n')

    for dep_name, dep_info in dependencies:
        use_deps = ["CONAN_PKG::%s" % d for d in dep_info.public_deps]
        deps = "" if not use_deps else " ".join(use_deps)
        section.append(_target_template.format(name="CONAN_PKG::%s" % dep_name, deps=deps,
                                               uname=dep_name.upper(), pkg_name=dep_name))

    all_targets = " ".join(["CONAN_PKG::%s" % name for name, _ in dependencies])
    section.append('    set(CONAN_TARGETS %s)\n' % all_targets)
    section.append('endmacro()\n')
    return section


_cmake_common_macros = """

function(conan_find_libraries_abs_path libraries package_libdir libraries_abs_path)
    foreach(_LIBRARY_NAME ${libraries})
        unset(CONAN_FOUND_LIBRARY CACHE)
        find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                     NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
        if(CONAN_FOUND_LIBRARY)
            message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${CONAN_FOUND_LIBRARY})
        else()
            message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
        endif()
    endforeach()
    unset(CONAN_FOUND_LIBRARY CACHE)
    set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
endfunction()

function(conan_package_library_targets libraries package_libdir libraries_abs_path deps build_type package_name)
    foreach(_LIBRARY_NAME ${libraries})
        unset(CONAN_FOUND_LIBRARY CACHE)
        find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                     NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
        if(CONAN_FOUND_LIBRARY)
            message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
            set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${build_type})
            add_library(${_LIB_NAME} UNKNOWN IMPORTED)
            set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
            string(REPLACE " " ";" deps_list "${deps}")
            set_property(TARGET ${_LIB_NAME} PROPERTY INTERFACE_LINK_LIBRARIES ${deps_list})
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIB_NAME})
        else()
            message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
        endif()
    endforeach()
    unset(CONAN_FOUND_LIBRARY CACHE)
    set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
endfunction()

macro(conan_global_flags)
    if(CONAN_SYSTEM_INCLUDES)
        include_directories(SYSTEM ${CONAN_INCLUDE_DIRS}
                                   "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
    else()
        include_directories(${CONAN_INCLUDE_DIRS}
                            "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
    endif()

    link_directories(${CONAN_LIB_DIRS})

    conan_find_libraries_abs_path("${CONAN_LIBS_DEBUG}" "${CONAN_LIB_DIRS_DEBUG}"
                                  CONAN_LIBS_DEBUG)
    conan_find_libraries_abs_path("${CONAN_LIBS_RELEASE}" "${CONAN_LIB_DIRS_RELEASE}"
                                  CONAN_LIBS_RELEASE)

    add_compile_options(${CONAN_DEFINES}
                        "$<$<CONFIG:Debug>:${CONAN_DEFINES_DEBUG}>"
                        "$<$<CONFIG:Release>:${CONAN_DEFINES_RELEASE}>"
                        "$<$<CONFIG:RelWithDebInfo>:${CONAN_DEFINES_RELEASE}>"
                        "$<$<CONFIG:MinSizeRel>:${CONAN_DEFINES_RELEASE}>")

    conan_set_flags("")
    conan_set_flags("_RELEASE")
    conan_set_flags("_DEBUG")

endmacro()

macro(conan_target_link_libraries target)
    if(CONAN_TARGETS)
        target_link_libraries(${target} ${CONAN_TARGETS})
    else()
        target_link_libraries(${target} ${CONAN_LIBS})
        foreach(_LIB ${CONAN_LIBS_RELEASE})
            target_link_libraries(${target} optimized ${_LIB})
        endforeach()
        foreach(_LIB ${CONAN_LIBS_DEBUG})
            target_link_libraries(${target} debug ${_LIB})
        endforeach()
    endif()
endmacro()
"""

cmake_basic_setup = """
macro(conan_basic_setup)
    set(options TARGETS NO_OUTPUT_DIRS SKIP_RPATH KEEP_RPATHS SKIP_STD SKIP_FPIC)
    cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
    conan_check_compiler()
    if(NOT ARGUMENTS_NO_OUTPUT_DIRS)
        conan_output_dirs_setup()
    endif()
    conan_set_find_library_paths()
    if(NOT ARGUMENTS_TARGETS)
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()
    if(ARGUMENTS_SKIP_RPATH)
        # Change by "DEPRECATION" or "SEND_ERROR" when we are ready
        message(WARNING "Conan: SKIP_RPATH is deprecated, it has been renamed to KEEP_RPATHS")
    endif()
    if(NOT ARGUMENTS_SKIP_RPATH AND NOT ARGUMENTS_KEEP_RPATHS)
        # Parameter has renamed, but we keep the compatibility with old SKIP_RPATH
        message(STATUS "Conan: Adjusting default RPATHs Conan policies")
        conan_set_rpath()
    endif()
    if(NOT ARGUMENTS_SKIP_STD)
        message(STATUS "Conan: Adjusting language standard")
        conan_set_std()
    endif()
    if(NOT ARGUMENTS_SKIP_FPIC)
        conan_set_fpic()
    endif()
    conan_set_vs_runtime()
    conan_set_libcxx()
    conan_set_find_paths()
endmacro()
"""


cmake_basic_setup_deps = """
    macro(conan_basic_setup_deps)
        set(options TARGETS)
        cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )
        if(CONAN_EXPORTED)
            message(STATUS "Conan: called by CMake conan helper")
        endif()
        conan_set_find_library_paths()
        if(NOT ARGUMENTS_TARGETS)
            message(STATUS "Conan: Using cmake global configuration")
            conan_global_flags()
        else()
            message(STATUS "Conan: Using cmake targets configuration")
            conan_define_targets()
        endif()
        conan_set_find_paths()
    endmacro()
"""

cmake_macros = """

macro(conan_set_find_paths)
    # CMAKE_MODULE_PATH does not have Debug/Release config, but there are variables
    # CONAN_CMAKE_MODULE_PATH_DEBUG to be used by the consumer
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})

    # Set the find root path (cross build)
    set(CMAKE_FIND_ROOT_PATH ${CONAN_CMAKE_FIND_ROOT_PATH} ${CMAKE_FIND_ROOT_PATH})
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM)
        set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY)
        set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE)
        set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE})
    endif()
endmacro()

macro(conan_set_find_library_paths)
    # CMAKE_INCLUDE_PATH, CMAKE_LIBRARY_PATH does not have Debug/Release config, but there are variables
    # CONAN_INCLUDE_DIRS_DEBUG/RELEASE CONAN_LIB_DIRS_DEBUG/RELEASE to be used by the consumer
    # For find_library
    set(CMAKE_INCLUDE_PATH ${CONAN_INCLUDE_DIRS} ${CMAKE_INCLUDE_PATH})
    set(CMAKE_LIBRARY_PATH ${CONAN_LIB_DIRS} ${CMAKE_LIBRARY_PATH})
endmacro()


""" + _cmake_common_macros


cmake_macros_multi = """
if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_release.cmake)
    include(${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_release.cmake)
else()
    message(FATAL_ERROR "No conanbuildinfo_release.cmake, please install the Release conf first")
endif()
if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_debug.cmake)
    include(${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_debug.cmake)
else()
    message(FATAL_ERROR "No conanbuildinfo_debug.cmake, please install the Debug conf first")
endif()

macro(conan_basic_setup)
    set(options TARGETS)
    cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
    conan_check_compiler()
    # conan_output_dirs_setup()
    if(NOT ARGUMENTS_TARGETS)
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()
    conan_set_rpath()
    conan_set_vs_runtime()
    conan_set_libcxx()
    conan_set_find_paths()
    conan_set_fpic()
endmacro()

macro(conan_set_vs_runtime)
    # This conan_set_vs_runtime is MORE opinionated than the regular one. It will
    # Leave the defaults MD (MDd) or replace them with MT (MTd) but taking into account the
    # debug, forcing MXd for debug builds. It will generate MSVCRT warnings if the dependencies
    # are installed with "conan install" and the wrong build time.
    if(CONAN_LINK_RUNTIME MATCHES "MT")
        foreach(flag CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
                     CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
                     CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL)
            if(DEFINED ${flag})
                string(REPLACE "/MD" "/MT" ${flag} "${${flag}}")
            endif()
        endforeach()
        foreach(flag CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG)
            if(DEFINED ${flag})
                string(REPLACE "/MDd" "/MTd" ${flag} "${${flag}}")
            endif()
        endforeach()
    endif()
endmacro()

macro(conan_set_find_paths)
    if(CMAKE_BUILD_TYPE)
        if(${CMAKE_BUILD_TYPE} MATCHES "Debug")
            set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_PREFIX_PATH})
            set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_MODULE_PATH})
        else()
            set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_PREFIX_PATH})
            set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_MODULE_PATH})
        endif()
    endif()
endmacro()
""" + _cmake_common_macros
