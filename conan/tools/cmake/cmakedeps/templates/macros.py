import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

cmakedeps_macros.cmake

"""


class MacrosTemplate(CMakeDepsFileTemplate):
    """cmakedeps_macros.cmake"""

    def __init__(self):
        super(MacrosTemplate, self).__init__(cmakedeps=None, require=None, conanfile=None)

    @property
    def filename(self):
        return "cmakedeps_macros.cmake"

    @property
    def context(self):
        return {}

    @property
    def template(self):
        return textwrap.dedent("""
        function(conan_message MESSAGE_TYPE MESSAGE_CONTENT)
            if(NOT CONAN_CMAKE_SILENT_OUTPUT)
                message(${MESSAGE_TYPE} "${MESSAGE_CONTENT}")
            endif()
        endfunction()

       macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
           if(APPLE)
               foreach(_FRAMEWORK ${FRAMEWORKS})
                   # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                   find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAMES ${_FRAMEWORK} PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
                   if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                       list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                       conan_message(DEBUG "Framework found! ${FRAMEWORKS_FOUND}")
                   else()
                       conan_message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${FRAMEWORKS_DIRS}")
                   endif()
               endforeach()
           endif()
       endmacro()

       function(conan_package_library_targets libraries package_libdir package_bindir library_type is_host_windows deps out_libraries out_libraries_target config_suffix package_name)
           set(_out_libraries "")
           set(_out_libraries_target "")
           set(_CONAN_ACTUAL_TARGETS "")

           foreach(_LIBRARY_NAME ${libraries})
               find_library(CONAN_FOUND_LIBRARY NAMES ${_LIBRARY_NAME} PATHS ${package_libdir}
                            NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
               if(CONAN_FOUND_LIBRARY)
                   conan_message(DEBUG "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
                   list(APPEND _out_libraries ${CONAN_FOUND_LIBRARY})

                   # Create a micro-target for each lib/a found
                   # Allow only some characters for the target name
                   string(REGEX REPLACE "[^A-Za-z0-9.+_-]" "_" _LIBRARY_NAME ${_LIBRARY_NAME})
                   set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${config_suffix})
                   if(NOT TARGET ${_LIB_NAME})
                       if(library_type STREQUAL "SHARED" AND is_host_windows)
                         set(CMAKE_FIND_LIBRARY_SUFFIXES .dll ${CMAKE_FIND_LIBRARY_SUFFIXES})
                         find_library(CONAN_SHARED_FOUND_LIBRARY NAMES ${_LIBRARY_NAME} PATHS ${package_bindir}
                                      NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
                         if(NOT CONAN_SHARED_FOUND_LIBRARY)
                           conan_message(STATUS "Cannot locate shared library: ${_LIBRARY_NAME}")
                           set(CONAN_DLL_NOT_FOUND 1)
                         endif()
                       endif()

                       # Create a micro-target for each lib/a found
                       if (CONAN_SHARED_FOUND_LIBRARY)
                           add_library(${_LIB_NAME} SHARED IMPORTED)
                           set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_SHARED_FOUND_LIBRARY})
                           set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_IMPLIB ${CONAN_FOUND_LIBRARY})
                           conan_message(DEBUG "Found DLL and STATIC at ${CONAN_SHARED_FOUND_LIBRARY}, ${CONAN_FOUND_LIBRARY}")
                        else()
                           if(CONAN_DLL_NOT_FOUND)
                               # If we haven't found the DLL, fallback to old behavior: UNKNOWN target linking the static
                               add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                               conan_message(DEBUG "DLL library not found, creating UNKNOWN IMPORTED target")
                           else()
                               # library_type can be STATIC, still UNKNOWN (if no package type available in the recipe) or SHARED (no windows)
                               add_library(${_LIB_NAME} ${library_type} IMPORTED)
                               conan_message(DEBUG "Created target ${_LIB_NAME} ${library_type} IMPORTED")
                           endif()
                           set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                       endif()



                       list(APPEND _CONAN_ACTUAL_TARGETS ${_LIB_NAME})
                   else()
                       conan_message(STATUS "Skipping already existing target: ${_LIB_NAME}")
                   endif()
                   list(APPEND _out_libraries_target ${_LIB_NAME})
                   conan_message(DEBUG "Found: ${CONAN_FOUND_LIBRARY}")
               else()
                   conan_message(FATAL_ERROR "Library '${_LIBRARY_NAME}' not found in package. If '${_LIBRARY_NAME}' is a system library, declare it with 'cpp_info.system_libs' property")
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
